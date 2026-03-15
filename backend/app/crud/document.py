from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.models.document import Document as DBDocument
from app.db.models.tag import Tag as DBTag
from app.schemas.document import DocumentCreate, DocumentUpdate

class CRUDDocument:
    async def get(self, db: AsyncSession, document_id: int) -> Optional[DBDocument]:
        result = await db.execute(
            select(DBDocument)
            .options(
                selectinload(DBDocument.tags),
                selectinload(DBDocument.summary),
                selectinload(DBDocument.document_metadata)
            ) # Eager load everything needed for the UI
            .filter(DBDocument.id == document_id)
        )
        return result.scalars().first()

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DBDocument]:
        result = await db.execute(
            select(DBDocument)
            .options(
                selectinload(DBDocument.tags),
                selectinload(DBDocument.summary),
                selectinload(DBDocument.document_metadata)
            ) # Eager load everything needed for the UI
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, document_in: DocumentCreate, uploaded_by_user_id: int, organization_id: Optional[int] = None) -> DBDocument:
        db_document = DBDocument(
            filename=document_in.filename,
            s3_url=str(document_in.s3_url),
            case_id=document_in.case_id,
            uploaded_by_user_id=uploaded_by_user_id,
            organization_id=organization_id,
            content=document_in.content,
            classification=document_in.classification,
            language=document_in.language,
            page_count=document_in.page_count,
        )
        db.add(db_document)
        await db.commit()
        await db.refresh(db_document)
        return db_document

    async def update(self, db: AsyncSession, document_id: int, document_in: DocumentUpdate) -> Optional[DBDocument]:
        db_document = await self.get(db, document_id)
        if not db_document:
            return None
        
        update_data = document_in.model_dump(exclude_unset=True)
        if "s3_url" in update_data:
            update_data["s3_url"] = str(update_data["s3_url"])

        for field, value in update_data.items():
            setattr(db_document, field, value)
        
        await db.commit()
        await db.refresh(db_document)
        return db_document

    async def delete(self, db: AsyncSession, document_id: int) -> Optional[DBDocument]:
        db_document = await self.get(db, document_id)
        if not db_document:
            return None
        await db.delete(db_document)
        await db.commit()
        return db_document

    async def add_tag_to_document(self, db: AsyncSession, document_id: int, tag_id: int) -> Optional[DBDocument]:
        db_document = await self.get(db, document_id)
        if not db_document:
            return None
        
        result = await db.execute(select(DBTag).filter(DBTag.id == tag_id))
        db_tag = result.scalars().first()
        if not db_tag:
            return None
        
        db_document.tags.append(db_tag)
        await db.commit()
        await db.refresh(db_document)
        return db_document

    async def remove_tag_from_document(self, db: AsyncSession, document_id: int, tag_id: int) -> Optional[DBDocument]:
        db_document = await self.get(db, document_id)
        if not db_document:
            return None
        
        result = await db.execute(select(DBTag).filter(DBTag.id == tag_id))
        db_tag = result.scalars().first()
        if not db_tag:
            return None
        
        if db_tag in db_document.tags:
            db_document.tags.remove(db_tag)
            await db.commit()
            await db.refresh(db_document)
        return db_document

    async def semantic_search(self, db: AsyncSession, query_embedding: List[float], case_id: Optional[int] = None, limit: int = 10) -> List[DBDocument]:
        # Temporarily disabling this code as semantic search will be moved to the DocumentChunk model
        return []
    
    async def full_text_search(
        self,
        db: AsyncSession,
        query_string: str,
        case_id: Optional[int] = None,
        language: Optional[str] = None,
        classification: Optional[str] = None,
        tag_names: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[DBDocument]:
        search_query = select(DBDocument).options(selectinload(DBDocument.tags))

        # Basic full-text search using ilike on content and filename
        search_query = search_query.filter(
            (DBDocument.content.ilike(f"%{query_string}%")) |
            (DBDocument.filename.ilike(f"%{query_string}%"))
        )

        if case_id:
            search_query = search_query.filter(DBDocument.case_id == case_id)
        if language:
            search_query = search_query.filter(DBDocument.language == language)
        if classification:
            search_query = search_query.filter(DBDocument.classification == classification)
        if tag_names:
            # This is a basic filter for tags. For proper filtering with multiple tags,
            # a more complex join or subquery might be needed depending on requirements.
            for tag_name in tag_names:
                search_query = search_query.filter(DBDocument.tags.any(DBTag.name == tag_name))

        search_query = search_query.offset(skip).limit(limit)
        result = await db.execute(search_query)
        return list(result.scalars().all())


document_crud = CRUDDocument()
