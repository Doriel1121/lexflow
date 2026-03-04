from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import document_tag_association
from app.db.models.tag import Tag as DBTag
from app.schemas.tag import TagCreate, TagUpdate


class CRUDTag:
    async def get(self, db: AsyncSession, tag_id: int) -> Optional[DBTag]:
        result = await db.execute(select(DBTag).filter(DBTag.id == tag_id))
        return result.scalars().first()

    async def get_by_name(self, db: AsyncSession, name: str, organization_id: Optional[int] = None) -> Optional[DBTag]:
        query = select(DBTag).filter(DBTag.name == name)
        if organization_id is not None and hasattr(DBTag, "organization_id"):
            query = query.filter(DBTag.organization_id == organization_id)
        result = await db.execute(query)
        return result.scalars().first()

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DBTag]:
        result = await db.execute(select(DBTag).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, tag_in: TagCreate) -> DBTag:
        db_tag = DBTag(name=tag_in.name)
        if tag_in.category:
            db_tag.category = tag_in.category
        db.add(db_tag)
        await db.commit()
        await db.refresh(db_tag)
        return db_tag

    async def update(self, db: AsyncSession, tag_id: int, tag_in: TagUpdate) -> Optional[DBTag]:
        db_tag = await self.get(db, tag_id)
        if not db_tag:
            return None

        update_data = tag_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_tag, field, value)

        await db.commit()
        await db.refresh(db_tag)
        return db_tag

    async def delete(self, db: AsyncSession, tag_id: int) -> Optional[DBTag]:
        db_tag = await self.get(db, tag_id)
        if not db_tag:
            return None
        await db.delete(db_tag)
        await db.commit()
        return db_tag

    async def get_multi_by_organization(
        self,
        db: AsyncSession,
        organization_id: int,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
    ) -> List[DBTag]:
        """
        Return tags scoped to an organisation, optionally filtered by category.
        Each returned Tag ORM object is enriched with a transient `document_count`
        attribute so the Pydantic schema can serialise it.
        """
        # Subquery: count documents per tag via the association table
        doc_count_sq = (
            select(
                document_tag_association.c.tag_id,
                func.count(document_tag_association.c.document_id).label("doc_count"),
            )
            .group_by(document_tag_association.c.tag_id)
            .subquery()
        )

        query = (
            select(DBTag, func.coalesce(doc_count_sq.c.doc_count, 0).label("doc_count"))
            .outerjoin(doc_count_sq, DBTag.id == doc_count_sq.c.tag_id)
            .offset(skip)
            .limit(limit)
        )

        if hasattr(DBTag, "organization_id"):
            query = query.filter(DBTag.organization_id == organization_id)

        if category:
            query = query.filter(DBTag.category == category)

        result = await db.execute(query)
        rows = result.all()

        tags: List[DBTag] = []
        for row in rows:
            tag = row[0]
            count = int(row[1])
            # Attach the count as a plain attribute so Pydantic picks it up
            tag.document_count = count
            tags.append(tag)

        return tags

    async def find_or_create(
        self,
        db: AsyncSession,
        name: str,
        category: Optional[str] = None,
        organization_id: Optional[int] = None,
    ) -> DBTag:
        """Find an existing tag (scoped to org) or create one."""
        # Scope lookup by org so tags from different orgs never collide
        tag = await self.get_by_name(db, name, organization_id=organization_id)
        if tag:
            # Update category if a more specific one is now known
            if category and getattr(tag, "category", None) != category:
                tag.category = category
                await db.commit()
                await db.refresh(tag)
            return tag

        db_tag = DBTag(name=name)
        if category:
            db_tag.category = category
        if hasattr(DBTag, "organization_id") and organization_id is not None:
            db_tag.organization_id = organization_id

        db.add(db_tag)
        await db.commit()
        await db.refresh(db_tag)
        return db_tag



crud_tag = CRUDTag()
