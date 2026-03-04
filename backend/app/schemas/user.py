from typing import Optional
from pydantic import BaseModel, EmailStr
from app.db.models.user import UserRole

class OrganizationInfo(BaseModel):
    id: int
    name: str
    slug: str
    
    class Config:
        from_attributes = True

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    social_id: Optional[str] = None
    provider: Optional[str] = None
    role: Optional[UserRole] = UserRole.LAWYER

class UserUpdate(UserBase):
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    social_id: Optional[str] = None
    provider: Optional[str] = None
    role: Optional[UserRole] = None

class UserInDB(UserBase):
    id: int
    hashed_password: str
    is_active: bool
    is_superuser: bool
    social_id: Optional[str] = None
    provider: Optional[str] = None
    role: UserRole

    class Config:
        from_attributes = True

class User(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    social_id: Optional[str] = None
    provider: Optional[str] = None
    role: UserRole
    organization_id: Optional[int] = None
    organization: Optional[OrganizationInfo] = None

    class Config:
        from_attributes = True
