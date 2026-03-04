from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.case import Case as DBCase, CaseNote as DBCaseNote
from app.db.models.document import Document as DBDocument
from app.schemas.case import CaseCreate, CaseUpdate, CaseNoteCreate, CaseNoteUpdate

class CRUDCase:
    async def get(self, db: AsyncSession, case_id: int) -> Optional[DBCase]:
        result = await db.execute(select(DBCase).filter(DBCase.id == case_id))
        return result.scalars().first()

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DBCase]:
        result = await db.execute(select(DBCase).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, case_in: CaseCreate, user_id: int, org_id: Optional[int] = None) -> DBCase:
        db_case = DBCase(
            title=case_in.title,
            description=case_in.description,
            status=case_in.status if isinstance(case_in.status, str) else case_in.status.value,
            client_id=case_in.client_id,
            created_by_user_id=user_id,
            organization_id=org_id,
        )
        db.add(db_case)
        await db.commit()
        await db.refresh(db_case)
        return db_case

    async def update(self, db: AsyncSession, case_id: int, case_in: CaseUpdate) -> Optional[DBCase]:
        db_case = await self.get(db, case_id)
        if not db_case:
            return None
        
        update_data = case_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_case, field, value)
        
        await db.commit()
        await db.refresh(db_case)
        return db_case

    async def delete(self, db: AsyncSession, case_id: int) -> Optional[DBCase]:
        db_case = await self.get(db, case_id)
        if not db_case:
            return None
        await db.delete(db_case)
        await db.commit()
        return db_case

    async def add_note_to_case(self, db: AsyncSession, case_id: int, note_in: CaseNoteCreate, user_id: int, org_id: Optional[int] = None) -> Optional[DBCaseNote]:
        db_case = await self.get(db, case_id)
        if not db_case:
            return None
        db_note = DBCaseNote(
            case_id=case_id,
            user_id=user_id,
            organization_id=org_id,
            content=note_in.content
        )
        db.add(db_note)
        await db.commit()
        await db.refresh(db_note)
        return db_note
    
    async def get_case_note(self, db: AsyncSession, note_id: int) -> Optional[DBCaseNote]:
        result = await db.execute(select(DBCaseNote).filter(DBCaseNote.id == note_id))
        return result.scalars().first()
    
    async def update_case_note(self, db: AsyncSession, note_id: int, note_in: CaseNoteUpdate) -> Optional[DBCaseNote]:
        db_note = await self.get_case_note(db, note_id)
        if not db_note:
            return None
        
        update_data = note_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_note, field, value)
        
        await db.commit()
        await db.refresh(db_note)
        return db_note
    
    async def delete_case_note(self, db: AsyncSession, note_id: int) -> Optional[DBCaseNote]:
        db_note = await self.get_case_note(db, note_id)
        if not db_note:
            return None
        await db.delete(db_note)
        await db.commit()
        return db_note

    async def assign_document_to_case(self, db: AsyncSession, case_id: int, document_id: int) -> Optional[DBCase]:
        db_case = await self.get(db, case_id)
        if not db_case:
            return None
        
        # This function assumes the document already exists and its case_id needs to be updated.
        # Alternatively, if a document is created for a case, its case_id would be set during creation.
        db_document = await db.execute(select(DBDocument).filter(DBDocument.id == document_id)).scalars().first()
        if not db_document:
            return None
        
        db_document.case_id = case_id
        await db.commit()
        await db.refresh(db_case) # Refresh the case to reflect the new document association
        return db_case


case_crud = CRUDCase()
