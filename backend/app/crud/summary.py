from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.summary import Summary as DBSummary
from app.schemas.summary import SummaryCreate, SummaryUpdate

class CRUDSummary:
    async def get(self, db: AsyncSession, summary_id: int) -> Optional[DBSummary]:
        result = await db.execute(select(DBSummary).filter(DBSummary.id == summary_id))
        return result.scalars().first()

    async def get_by_document_id(self, db: AsyncSession, document_id: int) -> Optional[DBSummary]:
        result = await db.execute(select(DBSummary).filter(DBSummary.document_id == document_id))
        return result.scalars().first()

    async def create(self, db: AsyncSession, summary_in: SummaryCreate) -> DBSummary:
        db_summary = DBSummary(
            document_id=summary_in.document_id,
            content=summary_in.content,
            key_dates=summary_in.key_dates,
            parties=summary_in.parties,
            missing_documents_suggestion=summary_in.missing_documents_suggestion,
        )
        db.add(db_summary)
        await db.commit()
        await db.refresh(db_summary)
        return db_summary

    async def update(self, db: AsyncSession, summary_id: int, summary_in: SummaryUpdate) -> Optional[DBSummary]:
        db_summary = await self.get(db, summary_id)
        if not db_summary:
            return None
        
        update_data = summary_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_summary, field, value)
        
        await db.commit()
        await db.refresh(db_summary)
        return db_summary

    async def delete(self, db: AsyncSession, summary_id: int) -> Optional[DBSummary]:
        db_summary = await self.get(db, summary_id)
        if not db_summary:
            return None
        await db.delete(db_summary)
        await db.commit()
        return db_summary

crud_summary = CRUDSummary()
