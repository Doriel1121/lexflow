"""
Integration-style tests for Smart Collections CRUD + API logic.

These tests use an in-memory SQLite database so they are fully self-contained —
no running Postgres required. They test the CRUD and service layer directly,
covering the same scenarios as the HTTP integration tests would.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.base import Base
from app.db.models.document import Document as DBDocument, document_tag_association
from app.db.models.tag import Tag as DBTag
from app.db.models.user import User as DBUser, UserRole
from app.db.models.organization import Organization as DBOrganization
from app.core.security import get_password_hash
from app.crud.tag import crud_tag
from app.schemas.tag import TagCreate

# ---------------------------------------------------------------------------
# In-process SQLite engine (no external DB needed)
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"

_engine = create_async_engine(SQLITE_URL, echo=False)
_Session = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test and drop them after."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    async with _Session() as session:
        yield session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_org(db: AsyncSession, name: str = "TestOrg") -> DBOrganization:
    import re, time
    slug = re.sub(r"[^a-z0-9]", "-", name.lower()) + f"-{int(time.time()*1000)}"
    org = DBOrganization(name=name, slug=slug)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


async def _make_user(db: AsyncSession, email: str, org_id: int) -> DBUser:
    user = DBUser(
        email=email,
        hashed_password=get_password_hash("pass"),
        full_name="Test User",
        is_active=True,
        role=UserRole.LAWYER,
        organization_id=org_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_doc(db: AsyncSession, user_id: int, org_id: int, filename: str = "test.pdf") -> DBDocument:
    doc = DBDocument(
        filename=filename,
        s3_url=f"http://storage.local/{filename}",
        uploaded_by_user_id=user_id,
        organization_id=org_id,
        content="Sample content.",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


# ---------------------------------------------------------------------------
# Tests — Tag CRUD
# ---------------------------------------------------------------------------

async def test_find_or_create_creates_tag_with_category(db: AsyncSession):
    """find_or_create should create a tag with the given category."""
    tag = await crud_tag.find_or_create(db, name="123456789", category="client_id")
    assert tag.id is not None
    assert tag.name == "123456789"
    assert tag.category == "client_id"


async def test_find_or_create_is_idempotent(db: AsyncSession):
    """Calling find_or_create twice should return the same tag."""
    t1 = await crud_tag.find_or_create(db, name="ProjectAlpha", category="project")
    t2 = await crud_tag.find_or_create(db, name="ProjectAlpha", category="project")
    assert t1.id == t2.id


async def test_get_multi_by_organization_category_filter(db: AsyncSession):
    """get_multi_by_organization should filter by category when requested."""
    org = await _make_org(db)

    t1 = DBTag(name="ID-111", category="client_id", organization_id=org.id)
    t2 = DBTag(name="ProjectX", category="project", organization_id=org.id)
    t3 = DBTag(name="AcmeCorp", category="organization", organization_id=org.id)
    db.add_all([t1, t2, t3])
    await db.commit()

    client_id_tags = await crud_tag.get_multi_by_organization(
        db, organization_id=org.id, category="client_id"
    )
    assert len(client_id_tags) == 1
    assert client_id_tags[0].name == "ID-111"
    assert client_id_tags[0].category == "client_id"


async def test_get_multi_by_organization_no_filter_returns_all(db: AsyncSession):
    """Without a category filter, all org tags should be returned."""
    org = await _make_org(db)

    for name, cat in [("A", "client_id"), ("B", "project"), ("C", "case_type")]:
        db.add(DBTag(name=name, category=cat, organization_id=org.id))
    await db.commit()

    all_tags = await crud_tag.get_multi_by_organization(db, organization_id=org.id)
    assert len(all_tags) == 3


async def test_get_multi_returns_document_count(db: AsyncSession):
    """Each tag returned should carry a correct document_count attribute."""
    org = await _make_org(db)
    user = await _make_user(db, "counttest@example.com", org.id)

    tag = DBTag(name="ContractType", category="case_type", organization_id=org.id)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)

    # Link 2 documents to the tag (reload with eager tags to avoid lazy-load error)
    from sqlalchemy import select as sa_select
    from sqlalchemy.orm import selectinload
    for i in range(2):
        doc = await _make_doc(db, user.id, org.id, f"doc{i}.pdf")
        result = await db.execute(
            sa_select(DBDocument).options(selectinload(DBDocument.tags)).filter(DBDocument.id == doc.id)
        )
        doc = result.scalars().first()
        doc.tags.append(tag)
    await db.commit()

    tags = await crud_tag.get_multi_by_organization(db, organization_id=org.id)
    assert len(tags) == 1
    assert tags[0].document_count == 2


async def test_document_count_zero_when_no_documents(db: AsyncSession):
    """A tag with no documents should have document_count == 0."""
    org = await _make_org(db)

    db.add(DBTag(name="EmptyTag", category="project", organization_id=org.id))
    await db.commit()

    tags = await crud_tag.get_multi_by_organization(db, organization_id=org.id)
    assert tags[0].document_count == 0


async def test_document_not_duplicated_across_collections(db: AsyncSession):
    """
    The same document can appear in multiple collections but the document
    record itself must exist only once.
    """
    org = await _make_org(db)
    user = await _make_user(db, "nodedup@example.com", org.id)
    doc = await _make_doc(db, user.id, org.id, "contract.pdf")

    tag_a = await crud_tag.find_or_create(db, "ProjectRiver", "project", org.id)
    tag_b = await crud_tag.find_or_create(db, "NDA", "document_type", org.id)

    # Avoid lazy-load issues by re-fetching with eager load
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(DBDocument).options(selectinload(DBDocument.tags)).filter(DBDocument.id == doc.id)
    )
    doc = result.scalars().first()
    doc.tags.append(tag_a)
    doc.tags.append(tag_b)
    await db.commit()

    # Document appears in both collections
    from sqlalchemy import select as sa_select
    for tag in [tag_a, tag_b]:
        stmt = (
            sa_select(DBDocument)
            .join(DBDocument.tags)
            .filter(DBTag.id == tag.id)
        )
        rows = (await db.execute(stmt)).scalars().all()
        assert len(rows) == 1
        assert rows[0].id == doc.id

    # But there's only ONE document record
    all_docs = (await db.execute(sa_select(DBDocument))).scalars().all()
    assert len(all_docs) == 1


# ---------------------------------------------------------------------------
# Tests — SmartCollectionsService integration (real DB)
# ---------------------------------------------------------------------------

async def test_smart_collections_service_assigns_tags_to_doc(db: AsyncSession):
    """
    SmartCollectionsService.route_document_to_collections should create and
    assign tags from the AI analysis using the real CRUD layer.
    """
    from app.services.smart_collections import SmartCollectionsService

    org = await _make_org(db)
    user = await _make_user(db, "svc_test@example.com", org.id)
    doc = await _make_doc(db, user.id, org.id)

    ai_analysis = {
        "parties": [
            {"name": "Acme Corp Ltd", "role": "Seller", "id_number": "123456789"},
        ],
        "document_type": "Contract",
        "document_subtype": "NDA",
    }

    svc = SmartCollectionsService()
    await svc.route_document_to_collections(db, doc, ai_analysis)

    # Reload and inspect tags
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(DBDocument).options(selectinload(DBDocument.tags)).filter(DBDocument.id == doc.id)
    )
    doc = result.scalars().first()

    categories = {t.category for t in doc.tags}
    assert "client_id" in categories
    assert "organization" in categories
    assert "case_type" in categories
    assert "document_type" in categories
