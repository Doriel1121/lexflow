from typing import List, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_active_superuser, get_current_active_user, RoleChecker
from app.schemas.user import UserCreate, UserUpdate, User as UserSchema
from app.crud.user import user_crud
from app.db.models.user import User as DBUser, UserRole

router = APIRouter()

@router.post("/", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN])),
):
    """
    Create a new user. Only accessible by superusers.
    """
    existing_user = await user_crud.get_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )
    user = await user_crud.create(db, user_in)
    return user

@router.get("/", response_model=List[UserSchema])
async def read_users(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN])),
):
    """
    Retrieve users. Only accessible by superusers.
    """
    users = await user_crud.get_multi(db, skip=skip, limit=limit)
    return users

@router.get("/me", response_model=UserSchema)
async def read_user_me(
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current active user with organization info.
    """
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from app.db.models.organization import Organization
    
    # Fetch user with organization relationship
    result = await db.execute(
        select(DBUser).options(selectinload(DBUser.organization)).where(DBUser.id == current_user.id)
    )
    user = result.scalar_one_or_none()
    
    return user

@router.get("/{user_id}", response_model=UserSchema)
async def read_user_by_id(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN])),
):
    """
    Get a specific user by ID. Only accessible by superusers.
    """
    user = await user_crud.get(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.put("/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN])),
):
    """
    Update a user. Only accessible by superusers.
    """
    user = await user_crud.update(db, user_id, user_in)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.delete("/{user_id}", response_model=UserSchema)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN])),
):
    """
    Delete a user. Only accessible by superusers.
    """
    user = await user_crud.delete(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
