from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.document_metadata import DocumentMetadata as DBDocumentMetadata
from app.schemas.document_metadata import DocumentMetadataCreate

class CRUDDocumentMetadata:
    async def get_by_document_id(self, db: AsyncSession, document_id: int) -> Optional[DBDocumentMetadata]:
        result = await db.execute(
            select(DBDocumentMetadata).filter(DBDocumentMetadata.document_id == document_id)
        )
        return result.scalars().first()

    async def create(self, db: AsyncSession, metadata_in: DocumentMetadataCreate) -> DBDocumentMetadata:
        db_metadata = DBDocumentMetadata(
            document_id=metadata_in.document_id,
            dates=metadata_in.dates,
            entities=metadata_in.entities,
            amounts=metadata_in.amounts,
            case_numbers=metadata_in.case_numbers,
        )
        db.add(db_metadata)
        await db.commit()
        await db.refresh(db_metadata)
        return db_metadata

    async def update(self, db: AsyncSession, document_id: int, metadata_in: DocumentMetadataCreate) -> Optional[DBDocumentMetadata]:
        db_metadata = await self.get_by_document_id(db, document_id)
        if not db_metadata:
            return None
        
        db_metadata.dates = metadata_in.dates
        db_metadata.entities = metadata_in.entities
        db_metadata.amounts = metadata_in.amounts
        db_metadata.case_numbers = metadata_in.case_numbers
        
        await db.commit()
        await db.refresh(db_metadata)
        return db_metadata

    async def delete(self, db: AsyncSession, document_id: int) -> Optional[DBDocumentMetadata]:
        db_metadata = await self.get_by_document_id(db, document_id)
        if not db_metadata:
            return None
        await db.delete(db_metadata)
        await db.commit()
        return db_metadata

crud_document_metadata = CRUDDocumentMetadata()
