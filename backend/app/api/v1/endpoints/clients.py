from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, RoleChecker
from app.schemas.client import ClientCreate, ClientUpdate, Client as ClientSchema
from app.crud.client import client_crud
from app.db.models.user import User as DBUser, UserRole

router = APIRouter()

@router.post("/", response_model=ClientSchema, status_code=status.HTTP_201_CREATED)
async def create_client(
    client_in: ClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER])),
):
    """
    Create a new client.
    """
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User does not belong to an organization")
        
    client_in_db = ClientCreate(**client_in.model_dump())
    client = await client_crud.create(db, obj_in=client_in_db, organization_id=current_user.organization_id)
    return client

@router.get("/", response_model=List[ClientSchema])
async def read_clients(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER])),
):
    """
    Retrieve clients.
    """
    if not current_user.organization_id:
        return []
    clients = await client_crud.get_multi_by_organization(
        db, organization_id=current_user.organization_id, skip=skip, limit=limit
    )
    return clients

@router.get("/{client_id}", response_model=ClientSchema)
async def read_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER])),
):
    """
    Get a specific client by ID.
    """
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User does not belong to an organization")
        
    client = await client_crud.get(db, id=client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return client

@router.put("/{client_id}", response_model=ClientSchema)
async def update_client(
    client_id: int,
    client_in: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER])),
):
    """
    Update a client.
    """
    client = await client_crud.get(db, id=client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    client = await client_crud.update(db, db_obj=client, obj_in=client_in)
    return client
