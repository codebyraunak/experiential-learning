import os
import re
import uuid
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import HTTPException, UploadFile

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
IMAGE_SIGNATURES = {
    "image/jpeg": lambda content: content.startswith(b"\xff\xd8\xff"),
    "image/png": lambda content: content.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda content: (
        len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    ),
}
DEFAULT_SUPABASE_BUCKET = "campusfix-complaint-photos"
_SAFE_FILENAME = re.compile(r"^[0-9a-f]{32}\.(?:jpg|png|webp)$")
_configured_upload_dir = Path(
    os.getenv("UPLOAD_DIR", str(Path(__file__).resolve().parents[1] / "uploads"))
)
if not _configured_upload_dir.is_absolute():
    _configured_upload_dir = Path(__file__).resolve().parents[1] / _configured_upload_dir
UPLOAD_DIR = _configured_upload_dir.resolve()


class SupabaseStorageError(RuntimeError):
    def __init__(self, status_code: int):
        super().__init__(f"Supabase Storage request failed with status {status_code}")
        self.status_code = status_code


def _supabase_config() -> tuple[str, str, str] | None:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", DEFAULT_SUPABASE_BUCKET).strip()
    bucket_was_configured = "SUPABASE_STORAGE_BUCKET" in os.environ
    if not url and not service_key and not bucket_was_configured:
        if os.getenv("RENDER", "").lower() == "true" or os.getenv(
            "APP_ENV", ""
        ).lower() == "production":
            raise RuntimeError(
                "Supabase Storage must be configured for production deployments"
            )
        return None
    if not url or not service_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must both be configured"
        )
    if not bucket:
        raise RuntimeError("SUPABASE_STORAGE_BUCKET must not be empty")
    return url, service_key, bucket


def _safe_filename(filename: str) -> bool:
    return bool(_SAFE_FILENAME.fullmatch(filename))


def _supabase_request(
    method: str,
    filename: str,
    *,
    content: bytes | None = None,
    delete: bool = False,
) -> httpx.Response:
    config = _supabase_config()
    if config is None:
        raise RuntimeError("Supabase Storage is not configured")
    url, service_key, bucket = config
    encoded_bucket = quote(bucket, safe="")
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
    }
    if delete:
        endpoint = f"{url}/storage/v1/object/{encoded_bucket}"
        response = httpx.request(
            method,
            endpoint,
            headers=headers,
            json={"prefixes": [filename]},
            timeout=20.0,
        )
    else:
        encoded_filename = quote(filename, safe="")
        endpoint = f"{url}/storage/v1/object/{encoded_bucket}/{encoded_filename}"
        if method == "POST":
            headers["Content-Type"] = _mime_type(filename)
            headers["x-upsert"] = "false"
        response = httpx.request(
            method,
            endpoint,
            headers=headers,
            content=content,
            timeout=20.0,
        )
    if response.status_code >= 400:
        raise SupabaseStorageError(response.status_code)
    return response


def _mime_type(filename: str) -> str:
    for mime_type, suffix in ALLOWED_IMAGE_TYPES.items():
        if filename.endswith(suffix):
            return mime_type
    raise ValueError("Unsupported complaint photo filename")


async def read_image(upload: UploadFile | None) -> tuple[bytes | None, str | None]:
    if upload is None:
        return None, None
    mime_type = (upload.content_type or "").lower()
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image")
    contents = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller")
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    if not IMAGE_SIGNATURES[mime_type](contents):
        raise HTTPException(status_code=415, detail="Image content does not match its file type")
    return contents, mime_type


def save_image(contents: bytes, mime_type: str) -> str:
    try:
        suffix = ALLOWED_IMAGE_TYPES[mime_type]
    except KeyError as exc:
        raise ValueError("Unsupported complaint photo type") from exc
    filename = f"{uuid.uuid4().hex}{suffix}"
    config = _supabase_config()
    if config is not None:
        _supabase_request("POST", filename, content=contents)
        return filename
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = (UPLOAD_DIR / filename).resolve()
    if path.parent != UPLOAD_DIR:
        raise RuntimeError("Invalid generated upload path")
    path.write_bytes(contents)
    return filename


def get_image(filename: str) -> tuple[bytes, str] | None:
    if not _safe_filename(filename):
        return None
    if _supabase_config() is not None:
        try:
            response = _supabase_request("GET", filename)
        except SupabaseStorageError as exc:
            if exc.status_code == 404:
                return None
            raise
        return response.content, _mime_type(filename)
    path = (UPLOAD_DIR / filename).resolve()
    if path.parent != UPLOAD_DIR or not path.is_file():
        return None
    return path.read_bytes(), _mime_type(filename)


def delete_image(filename: str | None) -> None:
    if filename is None or not _safe_filename(filename):
        return
    if _supabase_config() is not None:
        _supabase_request("DELETE", filename, delete=True)
        return
    path = (UPLOAD_DIR / filename).resolve()
    if path.parent == UPLOAD_DIR and path.exists():
        path.unlink()
