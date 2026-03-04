from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from datetime import timedelta

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
from app.core.dependencies import get_db, RoleChecker
from app.crud.user import user_crud
from app.db.models.user import User as DBUser, UserRole
from app.schemas.user import UserCreate

router = APIRouter()

class InviteRequest(BaseModel):
    email: EmailStr
    role: UserRole

class InviteAccept(BaseModel):
    token: str
    password: str
    full_name: str

@router.post("/")
async def send_invite(
    invite_in: InviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ORG_ADMIN, UserRole.ADMIN]))
) -> Any:
    """
    Invite a new member to the current user's organization.
    """
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="You do not belong to an organization.")
        
    # 1. Ensure user isn't already registered
    existing_user = await user_crud.get_by_email(db, email=invite_in.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists in the system.")
        
    # 2. Generate secure Invite Token valid for 7 days
    invite_token_expires = timedelta(days=7)
    invite_token = create_access_token(
        data={
            "sub": invite_in.email,
            "type": "invite",
            "org_id": current_user.organization_id,
            "role": invite_in.role.value if hasattr(invite_in.role, "value") else str(invite_in.role)
        },
        expires_delta=invite_token_expires
    )
    
    # 3. Simulate Email Send (Log it to terminal for now)
    invite_link = f"{settings.FRONTEND_ORIGINS.split(',')[0].strip()}/auth/accept-invite?token={invite_token}"
    
    print("\n" + "="*50)
    print(f"📧 SIMULATED EMAIL SENT TO: {invite_in.email}")
    print(f"Role: {invite_in.role}")
    print(f"Link: {invite_link}")
    print("="*50 + "\n")
    
    return {"message": "Invite sent successfully", "invite_link": invite_link}

@router.post("/accept")
async def accept_invite(
    accept_in: InviteAccept,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Consume an invite token to create a new user tied to the inviter's organization.
    """
    # 1. Decode and verify token
    payload = decode_access_token(accept_in.token)
    if not payload or payload.get("type") != "invite":
        raise HTTPException(status_code=400, detail="Invalid or expired invite token.")
        
    email = payload.get("sub")
    org_id = payload.get("org_id")
    role_str = payload.get("role")
    
    if not email or not org_id:
        raise HTTPException(status_code=400, detail="Malformed invite token.")
        
    # 2. Ensure they didn't try to register normally in the meantime
    existing = await user_crud.get_by_email(db, email=email.lower())
    if existing:
        raise HTTPException(status_code=400, detail="Account already registered. Please login.")
        
    # 3. Create the user
    new_user = UserCreate(
        email=email.lower(),
        password=accept_in.password,
        full_name=accept_in.full_name,
        role=UserRole(role_str) if role_str else UserRole.LAWYER
    )
    
    db_user = await user_crud.create(db, user_in=new_user, organization_id=org_id)
    
    return {"message": "Account created successfully. You may now login."}
