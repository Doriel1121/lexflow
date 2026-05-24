import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.document import Document as DBDocument, DocumentChunk
from app.db.models.user import User as DBUser
from app.db.models.summary import Summary as DBSummary
from app.db.models.document_metadata import DocumentMetadata as DBDocumentMetadata
from app.schemas.document import Document as DocumentSchema


@pytest.mark.asyncio
async def test_document_schema_validates_when_summary_and_metadata_eager_loaded(db_session):
    user = DBUser(email="test@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    doc = DBDocument(
        filename="testing file.pdf",
        s3_url="s3://bucket/testing.pdf",
        uploaded_by_user_id=user.id,
    )
    db_session.add(doc)
    await db_session.flush()

    db_session.add(
        DBSummary(
            document_id=doc.id,
            content="Summary text",
        )
    )
    db_session.add(
        DBDocumentMetadata(
            document_id=doc.id,
            dates=[{"value": "2026-01-01"}],
        )
    )
    db_session.add(
        DocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            text_content="chunk",
            embedding=[0.1] * 768,
        )
    )

    await db_session.commit()

    result = await db_session.execute(
        select(DBDocument).options(
            selectinload(DBDocument.summary),
            selectinload(DBDocument.document_metadata),
            selectinload(DBDocument.tags),
        )
    )
    loaded_doc = result.scalars().first()

    validated = DocumentSchema.model_validate(loaded_doc)
    assert validated.summary is not None
    assert validated.summary.content == "Summary text"
    assert validated.metadata is not None
    assert validated.metadata.dates == [{"value": "2026-01-01"}]

