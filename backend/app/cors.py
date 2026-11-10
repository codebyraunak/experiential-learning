import os
from urllib.parse import urlsplit


LOCAL_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)


def allowed_origins(configured_origins: str | None = None) -> list[str]:
    configured = (
        os.getenv("CORS_ORIGINS", "")
        if configured_origins is None
        else configured_origins
    )
    origins = list(LOCAL_ORIGINS)
    for candidate in configured.split(","):
        origin = candidate.strip().rstrip("/")
        if not origin:
            continue
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError(f"Invalid origin in CORS_ORIGINS: {candidate.strip()}")
        if origin not in origins:
            origins.append(origin)
    return origins
