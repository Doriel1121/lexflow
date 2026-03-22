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
        await log_audit(
            db=db,
            event_type="case_create",
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            resource_type="case",
            resource_id=str(case.id),
            metadata_json={"title": case.title}
        )
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
        "documents": [],
        "deadlines": []
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
        "documents": [],
        "deadlines": []
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
    from app.db.models.deadline import Deadline as DBDeadline
    case = await db.execute(
        select(DBCase)
        .options(
            selectinload(DBCase.notes), 
            selectinload(DBCase.documents),
            selectinload(DBCase.deadlines).selectinload(DBDeadline.document),
            selectinload(DBCase.assigned_lawyer),
            selectinload(DBCase.client)
        )
        .filter(DBCase.id == case_id)
    )
    case = case.scalars().first()
    
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    
    verify_resource_access(case, current_user)
    
    # Manually add documents and deadlines to response
    deadlines_with_doc = []
    for d in case.deadlines:
        d_dict = {
            "id": d.id,
            "deadline_date": d.deadline_date,
            "deadline_type": d.deadline_type,
            "description": d.description,
            "confidence_score": d.confidence_score,
            "document_id": d.document_id,
            "document_name": d.document.filename if d.document else "Unknown Document",
            "case_id": d.case_id,
            "organization_id": d.organization_id,
            "created_at": d.created_at,
            "updated_at": d.updated_at
        }
        deadlines_with_doc.append(d_dict)

    case_dict = {
        "id": case.id,
        "title": case.title,
        "description": case.description,
        "status": case.status.value if hasattr(case.status, 'value') else case.status,
        "client_id": case.client_id,
        "client_name": case.client.name if case.client else None,
        "created_by_user_id": case.created_by_user_id,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "notes": case.notes,
        "deadlines": deadlines_with_doc,
        "documents": [{
            "id": d.id,
            "filename": d.filename,
            "s3_url": d.s3_url,
            "classification": d.classification,
            "case_id": d.case_id
        } for d in case.documents],
        "assigned_lawyer_id": case.assigned_lawyer_id,
        "assigned_lawyer_name": case.assigned_lawyer.full_name if case.assigned_lawyer else None,
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
    await log_audit(
        db=db,
        event_type="case_update",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        resource_type="case",
        resource_id=str(case.id),
        metadata_json={"changes": case_in.model_dump(exclude_unset=True)}
    )
    
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
    await log_audit(
        db=db,
        event_type="case_delete",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        resource_type="case",
        resource_id=str(case_id),
        metadata_json={}
    )
    
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
    await log_audit(
        db=db,
        event_type="case_assign_document",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        resource_type="case",
        resource_id=str(case_id),
        metadata_json={"document_id": document_id}
    )
    
    return case


# ---------------------------------------------------------------------------
# New Smart Feature Endpoints
# ---------------------------------------------------------------------------

from pydantic import BaseModel
from typing import Optional as Opt

class AssignLawyerRequest(BaseModel):
    lawyer_id: Opt[int] = None  # None to unassign

class BulkUpdateRequest(BaseModel):
    case_ids: List[int]
    assigned_lawyer_id: Opt[int] = None
    status: Opt[str] = None


@router.get("/unassigned", response_model=List[CaseSchema])
async def get_unassigned_cases(
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN])),
    org_id: int = Depends(get_current_org),
    skip: int = 0,
    limit: int = 100,
):
    """
    List cases without an assigned lawyer. Org admin only.
    """
    from app.db.models.case import CaseStatus as CS
    result = await db.execute(
        select(DBCase).where(
            DBCase.organization_id == org_id,
            DBCase.assigned_lawyer_id == None,
            DBCase.status != CS.CLOSED,
        ).offset(skip).limit(limit)
    )
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
        "documents": [],
        "deadlines": [],
        "assigned_lawyer_id": None,
        "assigned_lawyer_name": None,
        "priority": c.priority if hasattr(c, 'priority') else "normal",
        "priority_score": c.priority_score if hasattr(c, 'priority_score') else 0.0,
    } for c in cases]


@router.patch("/{case_id}/assign-lawyer")
async def assign_lawyer_to_case(
    case_id: int,
    body: AssignLawyerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER])),
):
    """
    Assign (or unassign) a lawyer to a case. Creates timeline event + audit log.
    """
    case = await case_crud.get(db, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    verify_resource_access(case, current_user)

    old_lawyer_id = case.assigned_lawyer_id
    case.assigned_lawyer_id = body.lawyer_id
    await db.commit()
    await db.refresh(case)

    # Resolve lawyer name for response
    lawyer_name = None
    if body.lawyer_id:
        lawyer = await db.get(DBUser, body.lawyer_id)
        lawyer_name = lawyer.full_name if lawyer else None

    # Record case event
    from app.services.case_events import record_case_event
    await record_case_event(
        db=db,
        case_id=case_id,
        event_type="lawyer_assigned",
        description=f"Lawyer {'assigned' if body.lawyer_id else 'unassigned'}: {lawyer_name or 'None'}",
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        metadata_json={"old_lawyer_id": old_lawyer_id, "new_lawyer_id": body.lawyer_id},
    )

    # Audit log
    await log_audit(
        db=db,
        event_type="case_assign_lawyer",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        resource_type="case",
        resource_id=str(case_id),
        metadata_json={"old_lawyer_id": old_lawyer_id, "new_lawyer_id": body.lawyer_id}
    )

    # Recompute priority
    from app.services.priority_engine import priority_engine
    await priority_engine.compute_and_store(db, case_id)

    return {
        "id": case.id,
        "assigned_lawyer_id": case.assigned_lawyer_id,
        "assigned_lawyer_name": lawyer_name,
        "message": "Lawyer assigned successfully" if body.lawyer_id else "Lawyer unassigned",
    }


@router.post("/bulk-update")
async def bulk_update_cases(
    body: BulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: DBUser = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN])),
):
    """
    Bulk update multiple cases: assign lawyer, change status.
    """
    if not body.case_ids:
        raise HTTPException(status_code=400, detail="No case IDs provided")

    from app.services.case_events import record_case_event
    updated = 0

    for cid in body.case_ids:
        case = await case_crud.get(db, cid)
        if not case:
            continue
        try:
            verify_resource_access(case, current_user)
        except Exception:
            continue

        changes = {}

        if body.assigned_lawyer_id is not None:
            case.assigned_lawyer_id = body.assigned_lawyer_id
            changes["assigned_lawyer_id"] = body.assigned_lawyer_id

        if body.status is not None:
            old_status = case.status.value if hasattr(case.status, 'value') else case.status
            case.status = body.status.upper()
            changes["status"] = body.status.upper()

            await record_case_event(
                db=db, case_id=cid, event_type="status_changed",
                description=f"Status changed from {old_status} to {body.status.upper()}",
                user_id=current_user.id,
                organization_id=current_user.organization_id,
                metadata_json={"old_status": old_status, "new_status": body.status.upper()},
            )

        if changes:
            await db.commit()
            updated += 1

    # Audit log for bulk operation
    await log_audit(
        db=db,
        event_type="case_bulk_update",
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        resource_type="case",
        resource_id=",".join(str(i) for i in body.case_ids),
        metadata_json={"count": updated, "changes": {"lawyer_id": body.assigned_lawyer_id, "status": body.status}}
    )

    return {"updated": updated, "total": len(body.case_ids)}
