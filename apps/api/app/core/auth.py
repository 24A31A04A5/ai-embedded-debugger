import uuid
from typing import Annotated, Any

from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User


class FastApiRequestAdapter:
    """Adapts a FastAPI request to the interface expected by Clerk's authenticate_request."""

    def __init__(self, request: Request):
        self.headers = request.headers
        self.url = str(request.url)
        self.method = request.method


def get_clerk_client() -> Clerk:
    settings = get_settings()
    if not settings.clerk_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Clerk secret key is not configured.",
        )
    return Clerk(bearer_auth=settings.clerk_secret_key)


def verify_clerk_token(
    request: Request,
    clerk: Annotated[Clerk, Depends(get_clerk_client)],
) -> dict[str, Any]:
    """Verify the Clerk JWT and return the payload."""
    try:
        request_state = clerk.authenticate_request(
            FastApiRequestAdapter(request), AuthenticateRequestOptions()
        )
        if not request_state.is_signed_in:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        if not request_state.payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Empty token payload",
            )
        return request_state.payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {e}",
        ) from e


def get_current_user(
    payload: Annotated[dict[str, Any], Depends(verify_clerk_token)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Retrieve or create the User from the database based on the Clerk token."""
    clerk_id = payload.get("sub")
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing sub",
        )

    user = db.query(User).filter(User.clerk_id == clerk_id).first()

    if not user:
        email = payload.get("email") or f"{clerk_id}@placeholder.clerk.com"

        user = User(
            id=uuid.uuid4(),
            clerk_id=clerk_id,
            email=email,
            auth_provider="clerk",
            plan="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
