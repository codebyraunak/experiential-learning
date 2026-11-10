import os
import uuid
from pathlib import Path

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
_configured_upload_dir = Path(
    os.getenv("UPLOAD_DIR", str(Path(__file__).resolve().parents[1] / "uploads"))
)
if not _configured_upload_dir.is_absolute():
    _configured_upload_dir = Path(__file__).resolve().parents[1] / _configured_upload_dir
UPLOAD_DIR = _configured_upload_dir.resolve()


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
    suffix = ALLOWED_IMAGE_TYPES[mime_type]
    filename = f"{uuid.uuid4().hex}{suffix}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = (UPLOAD_DIR / filename).resolve()
    if path.parent != UPLOAD_DIR:
        raise RuntimeError("Invalid generated upload path")
    path.write_bytes(contents)
    return filename


def delete_image(filename: str | None) -> None:
    if filename is None:
        return
    path = (UPLOAD_DIR / filename).resolve()
    if path.parent == UPLOAD_DIR and path.exists():
        path.unlink()
