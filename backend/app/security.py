from fastapi import Header, HTTPException
from .config import ADMIN_TOKEN

def require_admin(authorization: str | None = Header(default=None)):
    if not authorization or authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(status_code=401, detail="Admin authentication required")
    return "admin"
