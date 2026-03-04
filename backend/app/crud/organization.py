import re
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.organization import Organization as DBOrganization
from app.schemas.organization import OrganizationCreate, OrganizationUpdate

def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from an organization name."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug.strip('-')

class CRUDOrganization:
    async def get(self, db: AsyncSession, org_id: int) -> Optional[DBOrganization]:
        result = await db.execute(select(DBOrganization).filter(DBOrganization.id == org_id))
        return result.scalars().first()

    async def get_by_slug(self, db: AsyncSession, slug: str) -> Optional[DBOrganization]:
        result = await db.execute(select(DBOrganization).filter(DBOrganization.slug == slug))
        return result.scalars().first()

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DBOrganization]:
        result = await db.execute(select(DBOrganization).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, obj_in: OrganizationCreate) -> DBOrganization:
        slug = generate_slug(obj_in.name)
        
        # Ensure slug is unique
        existing = await self.get_by_slug(db, slug)
        counter = 1
        original_slug = slug
        while existing:
            slug = f"{original_slug}-{counter}"
            existing = await self.get_by_slug(db, slug)
            counter += 1

        db_obj = DBOrganization(
            name=obj_in.name,
            slug=slug,
            is_active=True
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, org_id: int, obj_in: OrganizationUpdate) -> Optional[DBOrganization]:
        db_org = await self.get(db, org_id)
        if not db_org:
            return None
            
        update_data = obj_in.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"] != db_org.name:
            # Optionally update slug when name changes, but usually better to keep original slug to not break URLs
            pass
            
        for field, value in update_data.items():
            setattr(db_org, field, value)
            
        await db.commit()
        await db.refresh(db_org)
        return db_org

    async def delete(self, db: AsyncSession, org_id: int) -> Optional[DBOrganization]:
        db_org = await self.get(db, org_id)
        if not db_org:
            return None
        await db.delete(db_org)
        await db.commit()
        return db_org

organization_crud = CRUDOrganization()
