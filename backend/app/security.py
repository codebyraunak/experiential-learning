import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

bearer_scheme = HTTPBearer(auto_error=False)
TOKEN_LIFETIME = timedelta(hours=12)


@dataclass(frozen=True)
class Principal:
    role: str
    user_id: int | None
    display_name: str


def issue_access_token(role: str, user_id: int | None, display_name: str) -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY must be configured")

    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": display_name,
            "role": role,
            "uid": user_id,
            "iat": now,
            "exp": now + TOKEN_LIFETIME,
        },
        secret,
        algorithm="HS256",
    )


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Principal:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=503, detail="Authentication is not configured")

    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from error

    role = payload.get("role")
    user_id = payload.get("uid")
    if role == "admin":
        return Principal("admin", None, str(payload.get("sub", "admin")))
    if role == "student" and isinstance(user_id, int):
        student = db.get(models.Student, user_id)
        if student is not None and student.password_hash:
            return Principal("student", student.id, student.name)
    if role == "staff" and isinstance(user_id, int):
        staff = db.get(models.Staff, user_id)
        if staff is not None and staff.password_hash:
            return Principal("staff", staff.id, staff.name)
    raise HTTPException(status_code=401, detail="Account is unavailable")


def require_roles(*roles: str) -> Callable:
    def role_dependency(
        principal: Principal = Depends(get_current_principal),
    ) -> Principal:
        if principal.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return principal

    return role_dependency


def verify_admin_credentials(username: str, password: str) -> bool:
    configured_username = os.getenv("ADMIN_USERNAME", "")
    configured_password = os.getenv("ADMIN_PASSWORD", "")
    return bool(
        configured_username
        and configured_password
        and secrets.compare_digest(username, configured_username)
        and secrets.compare_digest(password, configured_password)
    )
