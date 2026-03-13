from typing import Generator, Annotated, List, Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import event
from jose import JWTError
from pydantic import ValidationError

from app.db.session import get_db
from app.db.models.user import User as DBUser
from app.schemas.token import TokenData
from app.core.config import settings
from app.core.security import decode_access_token
from app.db.models.user import UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)], token: Annotated[str, Depends(oauth2_scheme)]
) -> DBUser:
    """Return the user represented by the JWT token.

    The token payload may contain email **and/or** user_id.  Prefer looking up
    by primary key when available (safer in case the user changes their
    email).  Any validation errors result in a 401.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        if payload is None:
            raise credentials_exception
        token_data = TokenData(**payload)
    except (JWTError, ValidationError):
        raise credentials_exception
    
    # Mock user for no-db mode
    if token_data.email == "admin@lexflow.ai":
        return DBUser(
            id=1,
            email="admin@lexflow.ai",
            full_name="Admin User",
            is_active=True,
            is_superuser=True,
            role=UserRole.ADMIN
        )

    from sqlalchemy import select
    if token_data.user_id is not None:
        result = await db.execute(select(DBUser).filter(DBUser.id == token_data.user_id))
    else:
        result = await db.execute(select(DBUser).filter(DBUser.email == token_data.email))

    user = result.scalars().first()
    if not user:
        raise credentials_exception
    
    # Fix legacy users without a role set
    if user.role is None:
        user.role = UserRole.LAWYER  # default existing users to LAWYER
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    request.state.user = user
    return user

async def get_current_active_user(
    current_user: Annotated[DBUser, Depends(get_current_user)]
) -> DBUser:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    
    # Ensure role is set; NULL or missing role defaults to LAWYER
    if current_user.role is None:
        current_user.role = UserRole.LAWYER
    
    # Ensure the role is a known value (prevents bypassing RBAC with garbage data)
    try:
        if current_user.role not in list(UserRole):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")
    except (AttributeError, TypeError):
        # If role is corrupted, default to most restrictive (VIEWER)
        current_user.role = UserRole.VIEWER
    
    return current_user

async def get_current_active_superuser(
    current_user: Annotated[DBUser, Depends(get_current_active_user)]
) -> DBUser:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The user doesn't have enough privileges"
        )
    return current_user

async def get_current_org(
    current_user: Annotated[DBUser, Depends(get_current_active_user)]
) -> Optional[int]:
    """Extract organization_id from current user. Returns None for independent users."""
    return current_user.organization_id

def apply_org_filter(query, model, org_id: Optional[int]):
    """Apply organization filter to query if org_id exists."""
    if org_id is not None and hasattr(model, 'organization_id'):
        return query.where(model.organization_id == org_id)
    return query

def apply_user_org_filter(query, model, user_id: int, org_id: Optional[int], user_role: Optional[str] = None):
    """
    Apply organization or user filter based on user's organization membership.
    - If user is ADMIN/SUPERUSER: No filter (see everything)
    - If user has org_id: filter by organization_id
    - If user is independent: filter by uploaded_by_user_id or created_by_user_id
    """
    from app.db.models.user import UserRole
    
    # Admins and superusers see everything (no filtering)
    if user_role == UserRole.ADMIN.value or user_role == "admin":
        return query
    
    if org_id is not None and hasattr(model, 'organization_id'):
        # Organization member - see all org data
        return query.where(model.organization_id == org_id)
    else:
        # Independent user - see only own data
        if hasattr(model, 'uploaded_by_user_id'):
            return query.where(model.uploaded_by_user_id == user_id)
        elif hasattr(model, 'created_by_user_id'):
            return query.where(model.created_by_user_id == user_id)
        elif hasattr(model, 'user_id'):
            return query.where(model.user_id == user_id)
    return query

def verify_resource_access(resource, current_user: DBUser) -> None:
    """
    Verify if the current user has access to the given resource instance.
    Raises HTTPException (403) if access is denied.
    """
    from app.db.models.user import UserRole
    user_role = current_user.role.value if current_user.role else None
    
    # Admins and superusers see everything
    if getattr(current_user, "is_superuser", False) or user_role == UserRole.ADMIN.value or user_role == "admin":
        return
        
    org_id = current_user.organization_id
    user_id = current_user.id
    
    if org_id is not None and hasattr(resource, 'organization_id'):
        if resource.organization_id != org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        # Independent user check
        has_access = False
        if hasattr(resource, 'uploaded_by_user_id') and getattr(resource, 'uploaded_by_user_id') == user_id:
            has_access = True
        elif hasattr(resource, 'created_by_user_id') and getattr(resource, 'created_by_user_id') == user_id:
            has_access = True
        elif hasattr(resource, 'user_id') and getattr(resource, 'user_id') == user_id:
            has_access = True
            
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

class RoleChecker:
    """Dependency callable that enforces a user has one of the given roles.

    Superusers automatically bypass the check (they can do anything).  This
    allows endpoints to remain focused on business logic while the access
    policy lives in a central place.

    Usage::

        current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.LAWYER]))
    """

    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: Annotated[DBUser, Depends(get_current_active_user)]):
        # superuser bypass
        if getattr(user, "is_superuser", False):
            return user

        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Operation not permitted"
            )
        return user
