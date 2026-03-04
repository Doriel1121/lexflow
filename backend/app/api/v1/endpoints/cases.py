from typing import List, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_db, get_current_active_user, get_current_org, apply_user_org_filter, RoleChecker, verify_resource_access

from app.schemas.case import CaseCreate, CaseUpdate, Case as CaseSchema, CaseNoteCreate, CaseNote, CaseNoteUpdate
from app.crud.case import case_crud
from app.crud.user import user_crud
from app.db.models.user import User as DBUser, UserRole
from app.db.models.case import Case as DBCase, CaseNote as DBCaseNote
from app.services.audit import log_audit

router = APIRouter()

@router.get("/stats")
async def get_case_stats(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    org_id: int = Depends(get_current_org)
):
    """
    Get dashboard statistics.
    """
    from sqlalchemy import func
    from app.db.models.document import Document
    
    user_id = current_user.id
    user_role = current_user.role.value if current_user.role else None

    # Count active cases
    query = select(func.count(DBCase.id)).where(DBCase.status == "OPEN")
    query = apply_user_org_filter(query, DBCase, user_id, org_id, user_role)
    active_cases = await db.execute(query)
    active_count = active_cases.scalar() or 0

    # Count total documents
    query = select(func.count(Document.id))
    query = apply_user_org_filter(query, Document, user_id, org_id, user_role)
    total_docs = await db.execute(query)
    docs_count = total_docs.scalar() or 0

    # Count pending cases
    query = select(func.count(DBCase.id)).where(DBCase.status == "PENDING")
    query = apply_user_org_filter(query, DBCase, user_id, org_id, user_role)
    pending_cases = await db.execute(query)
    pending_count = pending_cases.scalar() or 0

    return {
        "active_cases": active_count,
        "total_documents": docs_count,
        "action_required": pending_count
    }

@router.post("/", response_model=CaseSchema, status_code=status.HTTP_201_CREATED)
async def create_case(
    case_in: CaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
    org_id: int = Depends(get_current_org)
):
    """
    Create a new case.
    """
    case = await case_crud.create(db, case_in, current_user.id, org_id)
    
    # Audit Log
    try:
        await log_audit(db, current_user, "case_create", {"case_id": case.id, "title": case.title})
    except Exception as e:
        print(f"Failed to create audit log: {e}")
    
    return {
        "id": case.id,
        "title": case.title,
        "description": case.description,
        "status": case.status.value if hasattr(case.status, 'value') else case.status,
        "client_id": case.client_id,
        "created_by_user_id": case.created_by_user_id,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "notes": [],
        "documents": []
    }

@router.get("/", response_model=List[CaseSchema])
async def read_cases(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
    org_id: int = Depends(get_current_org),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve cases.
    """
    user_id = current_user.id
    user_role = current_user.role.value if current_user.role else None
    query = select(DBCase).offset(skip).limit(limit)
    query = apply_user_org_filter(query, DBCase, user_id, org_id, user_role)
    result = await db.execute(query)
    cases = result.scalars().all()
    
    return [{
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "status": c.status.value if hasattr(c.status, 'value') else c.status,
        "client_id": c.client_id,
        "created_by_user_id": c.created_by_user_id,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
        "notes": [],
        "documents": []
    } for c in cases]

@router.get("/{case_id}", response_model=CaseSchema)
async def read_case_by_id(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker(list(UserRole))),
):
    """
    Get a specific case by ID.
    """
    from sqlalchemy.orm import selectinload
    case = await db.execute(
        select(DBCase)
        .options(selectinload(DBCase.notes), selectinload(DBCase.documents))
        .filter(DBCase.id == case_id)
    )
    case = case.scalars().first()
    
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    
    verify_resource_access(case, current_user)
    
    # Manually add documents to response
    case_dict = {
        "id": case.id,
        "title": case.title,
        "description": case.description,
        "status": case.status.value if hasattr(case.status, 'value') else case.status,
        "client_id": case.client_id,
        "created_by_user_id": case.created_by_user_id,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "notes": case.notes,
        "documents": [{
            "id": d.id,
            "filename": d.filename,
            "s3_url": d.s3_url,
            "classification": d.classification,
            "case_id": d.case_id
        } for d in case.documents]
    }
    return case_dict

@router.put("/{case_id}", response_model=CaseSchema)
async def update_case(
    case_id: int,
    case_in: CaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Update a case.
    """
    case = await case_crud.get(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    verify_resource_access(case, current_user)
    
    case = await case_crud.update(db, case_id, case_in)
    # Optional: Add authorization check if current_user has permission to update this case
    
    # Audit Log
    await log_audit(db, current_user, "case_update", {"case_id": case.id, "changes": case_in.model_dump(exclude_unset=True)})
    
    return case

@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Delete a case.
    """
    case = await case_crud.get(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    verify_resource_access(case, current_user)
    
    await case_crud.delete(db, case_id)
    # Optional: Add authorization check if current_user has permission to delete this case
    
    # Audit Log
    await log_audit(db, current_user, "case_delete", {"case_id": case_id})
    
    return

@router.post("/{case_id}/notes", response_model=CaseNote, status_code=status.HTTP_201_CREATED)
async def add_note_to_case(
    case_id: int,
    note_in: CaseNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
    org_id: int = Depends(get_current_org)
):
    """
    Add a note to a specific case.
    """
    case = await case_crud.get(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    verify_resource_access(case, current_user)

    note = await case_crud.add_note_to_case(db, case_id, note_in, current_user.id, org_id)
    return note

@router.put("/notes/{note_id}", response_model=CaseNote)
async def update_case_note(
    note_id: int,
    note_in: CaseNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Update a case note.
    """
    db_note = await case_crud.get_case_note(db, note_id)
    if not db_note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case note not found")
    verify_resource_access(db_note, current_user)
    
    note = await case_crud.update_case_note(db, note_id, note_in)
    return note

@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case_note(
    note_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Delete a case note.
    """
    db_note = await case_crud.get_case_note(db, note_id)
    if not db_note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case note not found")
    verify_resource_access(db_note, current_user)
    
    await case_crud.delete_case_note(db, note_id)
    return

@router.post("/{case_id}/assign-document/{document_id}", response_model=CaseSchema)
async def assign_document_to_case(
    case_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT])),
):
    """
    Assign an existing document to a case.
    (Note: This currently only updates the document's case_id,
    assuming the document already exists and is unassigned or being re-assigned.)
    """
    case = await case_crud.get(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    verify_resource_access(case, current_user)
    
    from app.crud.document import document_crud
    doc = await document_crud.get(db, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    verify_resource_access(doc, current_user)

    case = await case_crud.assign_document_to_case(db, case_id, document_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case or Document assignment failed")
        
    # Audit Log
    await log_audit(db, current_user, "case_assign_document", {"case_id": case_id, "document_id": document_id})
    
    return case
