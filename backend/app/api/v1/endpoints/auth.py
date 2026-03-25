from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    validate_password_strength,
)
from app.core.dependencies import get_db
from app.crud.user import user_crud
from app.schemas.user import UserCreate
from app.db.models.user import UserRole
from datetime import timedelta
import secrets
import httpx
from pydantic import BaseModel, EmailStr
from fastapi.security import OAuth2PasswordRequestForm

from app.core.rate_limit import enforce_login_rate_limit

from app.schemas.organization import OrganizationCreate
from app.crud.organization import organization_crud

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    organization_name: str

router = APIRouter()


def _cookie_settings() -> dict:
    """
    Cross-site cookies require SameSite=None and Secure=true.
    Use stricter settings outside development.
    """
    if settings.ENVIRONMENT == "development":
        return {"secure": False, "samesite": "lax"}
    return {"secure": True, "samesite": "none"}


@router.post("/register")
async def register(
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    """
    Register a new Organization and its first Admin User.
    """
    # Basic password policy
    try:
        validate_password_strength(user_in.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 1. Check if user already exists
    existing_user = await user_crud.get_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists."
        )
    
    # 2. Create the Organization
    org_in = OrganizationCreate(name=user_in.organization_name)
    org = await organization_crud.create(db, obj_in=org_in)
    
    # 3. Create the User and link to DB
    new_user = UserCreate(
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        role=UserRole.ORG_ADMIN
    )
    
    user = await user_crud.create(db, user_in=new_user, organization_id=org.id)

    # 4. Generate Tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    jwt_token = create_access_token(
        data={
            "email": user.email,
            "user_id": user.id,
            "org_id": user.organization_id,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role)
        },
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={
            "email": user.email,
            "user_id": user.id,
            "org_id": user.organization_id,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role)
        },
        expires_delta=refresh_expires
    )

    payload = {
        "access_token": jwt_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
        },
    }
    # For now we only return refresh token via HttpOnly cookie; frontend continues using access_token.
    # This is backwards compatible and sets us up for silent refresh later.
    target_response = response or Response()
    cookie_kwargs = _cookie_settings()
    target_response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=cookie_kwargs["secure"],
        samesite=cookie_kwargs["samesite"],
        max_age=int(refresh_expires.total_seconds()),
        path="/",
    )
    return payload

@router.post("/login")
async def login_native(
    request: Request,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    response: Response = None,
):
    """
    Standard OAuth2 compatible token login, get an access token for future requests.
    """
    from app.core.security import verify_password
    
    # Simple rate limiting by IP + username
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{form_data.username.lower()}"
    enforce_login_rate_limit(rate_key)

    user = await user_crud.get_by_email(db, email=form_data.username.lower())
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Fix legacy users without a role
    if user.role is None:
        user.role = UserRole.LAWYER
        await db.commit()
        await db.refresh(user)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    jwt_token = create_access_token(
        data={
            "email": user.email,
            "user_id": user.id,
            "org_id": user.organization_id,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role)
        },
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={
            "email": user.email,
            "user_id": user.id,
            "org_id": user.organization_id,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role)
        },
        expires_delta=refresh_expires
    )

    payload = {
        "access_token": jwt_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
        }
    }
    target_response = response or Response()
    cookie_kwargs = _cookie_settings()
    target_response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=cookie_kwargs["secure"],
        samesite=cookie_kwargs["samesite"],
        max_age=int(refresh_expires.total_seconds()),
        path="/",
    )
    return payload


@router.get("/login/{provider}")
def login(provider: str):
    """Initiate OAuth flow"""
    if provider == "google":
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise HTTPException(
                status_code=501,
                detail="Google OAuth not configured. Use Dev Login instead."
            )

        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={settings.GOOGLE_CLIENT_ID}&"
            f"redirect_uri=http://localhost:8000/v1/auth/callback/google&"
            f"response_type=code&"
            f"scope=openid%20email%20profile%20https://www.googleapis.com/auth/gmail.readonly&"
            f"access_type=offline&"
            f"prompt=consent"
        )
        return RedirectResponse(url=auth_url)
    elif provider == "microsoft":
        raise HTTPException(status_code=501, detail="Microsoft OAuth not configured. Use Dev Login instead.")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")


@router.get("/callback/{provider}")
async def auth_callback(
    provider: str,
    code: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth callback from provider"""
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing authorization code. Make sure you're coming from the OAuth provider."
        )
    
    if provider == "google":
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": "http://localhost:8000/v1/auth/callback/google",
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)
            token_json = token_response.json()

            if "error" in token_json:
                error_desc = token_json.get("error_description", token_json["error"])
                if token_json["error"] == "invalid_grant":
                    error_desc = f"Authorization code expired or invalid. Please try logging in again from the application. Error: {error_desc}"
                raise HTTPException(status_code=400, detail=error_desc)

            access_token = token_json["access_token"]
            refresh_token = token_json.get("refresh_token")
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_info = userinfo_response.json()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    email = user_info.get("email")
    social_id = user_info.get("id")

    if not email:
        raise HTTPException(status_code=400, detail="Email not found in OAuth response")

    user = await user_crud.get_by_email(db, email=email)
    if not user:
        user_in = UserCreate(
            email=email.lower(),
            password=secrets.token_urlsafe(16),
            full_name=user_info.get("name", email),
            social_id=social_id,
            provider=provider,
            role=UserRole.LAWYER,
        )
        user = await user_crud.create(db, user_in=user_in)
    
    # Store OAuth tokens for Gmail access
    user.google_access_token = access_token
    if refresh_token:
        user.google_refresh_token = refresh_token
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Fix legacy users without a role
    if user.role is None:
        user.role = UserRole.LAWYER
    
    # Extract role value before creating token
    user_role = user.role.value if hasattr(user.role, "value") else str(user.role)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jwt_token = create_access_token(
        data={
            "email": user.email,
            "user_id": user.id,
            "org_id": user.organization_id,
            "role": user_role
        },
        expires_delta=access_token_expires
    )

    frontend_url = f"{settings.FRONTEND_ORIGINS.split(',')[0].strip()}/auth/callback?token={jwt_token}"
    return RedirectResponse(url=frontend_url)


@router.get("/dev-login")
async def dev_login(
    email: str = "admin@lawfirm.com",
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    """
    Development-only login endpoint. Returns a real JWT for a real DB user.
    Creates the user if they don't exist.
    
    Note: Only admin@lawfirm.com gets ADMIN role. Other users get LAWYER role by default.
    This endpoint is disabled outside development environments.
    """
    # Hard guard: do not allow in non-development environments
    if settings.ENVIRONMENT != "development":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    user = await user_crud.get_by_email(db, email=email.lower())
    if not user:
        # Default to LAWYER role for regular users
        # Only hardcoded admin email gets ADMIN role
        default_role = UserRole.ADMIN if email == "admin@lawfirm.com" else UserRole.LAWYER
        is_superuser = email == "admin@lawfirm.com"
        
        user_in = UserCreate(
            email=email.lower(),
            password=secrets.token_urlsafe(16),
            full_name=email.split("@")[0].capitalize(),
            role=default_role,
        )
        user = await user_crud.create(db, user_in=user_in)
        
        # Set superuser status if needed
        if is_superuser:
            user.is_superuser = True
            await db.merge(user)
            await db.commit()

    # Ensure role is set
    if user.role is None:
        user.role = UserRole.LAWYER
        await db.merge(user)
        await db.commit()
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    jwt_token = create_access_token(
        data={
            "email": user.email,
            "user_id": user.id,
            "org_id": user.organization_id,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role)
        },
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={
            "email": user.email,
            "user_id": user.id,
            "org_id": user.organization_id,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role)
        },
        expires_delta=refresh_expires
    )

    payload = {
        "access_token": jwt_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
        },
    }

    target_response = response or Response()
    cookie_kwargs = _cookie_settings()
    target_response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=cookie_kwargs["secure"],
        samesite=cookie_kwargs["samesite"],
        max_age=int(refresh_expires.total_seconds()),
        path="/",
    )
    return payload


@router.post("/refresh")
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Exchange a refresh_token cookie for a new access token.
    Currently not used by the frontend, but implemented for future-proofing.
    """
    from jose import JWTError, jwt

    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = await user_crud.get(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={
            "email": user.email,
            "user_id": user.id,
            "org_id": user.organization_id,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        },
        expires_delta=access_token_expires,
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
    }
