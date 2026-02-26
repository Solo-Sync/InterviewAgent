from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def require_bearer_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> str:
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")

    expected_token = settings.api_bearer_token
    if expected_token and credentials.credentials != expected_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")

    return credentials.credentials
