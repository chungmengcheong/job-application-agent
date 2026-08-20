"""User authentication and authorization for FastAPI backend."""
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from backend.config import settings

# Set up the HTTP Bearer security scheme and allowed users/domains
security = HTTPBearer(auto_error=False)
GOOGLE_WEB_CLIENT_ID = settings.google_web_client_id
ALLOWED_EMAILS = settings.allowed_emails_set
ALLOWED_DOMAINS = settings.allowed_domains_set


def verify_token(creds: HTTPAuthorizationCredentials = Security(security)):
    """Authenticate user by verifying the Google ID token."""
    if not creds or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. No ID token provided."
        )
    token = creds.credentials
    try:
        claims = id_token.verify_oauth2_token(
            token,
            grequests.Request(),
            GOOGLE_WEB_CLIENT_ID,  # aud must equal your WEB client_id
        )
        if claims["iss"] not in {"accounts.google.com", "https://accounts.google.com"}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Wrong issuer"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid ID token for authentication: {e}"
        )
    return claims


def check_authorized_user(claims: dict = Depends(verify_token)) -> dict:
    """Authorize the user based on ALLOWED_EMAILS and ALLOWED_DOMAINS."""
    email = (claims.get("email") or "").lower()

    # email must be present and verified before allowlist checks run
    if not email or not claims.get("email_verified", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="There is an issue with your email address. Please login again.")

    # email is allowed
    if ALLOWED_EMAILS and email in ALLOWED_EMAILS:
        return claims
    if ALLOWED_DOMAINS and email.split("@")[-1] in ALLOWED_DOMAINS:
        return claims

    # email not authorized
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"{email} is not an authorized user. Please contact ccmmmail@gmail.com for access."
    )

