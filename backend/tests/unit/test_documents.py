import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.document import document_crud
from app.schemas.document import DocumentCreate
from app.db.models.document import Document as DBDocument


@pytest.mark.asyncio
async def test_create_document_with_page_count(db_session: AsyncSession):
    """Test creating a document with OCR metadata including page_count."""
    document_in = DocumentCreate(
        filename="test.pdf",
        s3_url="http://storage.local/test.pdf",
        case_id=1,
        content="Sample OCR text content",
        language="en",
        page_count=5,
        classification="contract"
    )
    
    document = await document_crud.create(db_session, document_in, uploaded_by_user_id=1)
    
    assert document.id is not None
    assert document.filename == "test.pdf"
    assert document.content == "Sample OCR text content"
    assert document.language == "en"
    assert document.page_count == 5
    assert document.classification == "contract"


@pytest.mark.asyncio
async def test_create_document_without_page_count(db_session: AsyncSession):
    """Test creating a document without page_count (should default to None)."""
    document_in = DocumentCreate(
        filename="test.txt",
        s3_url="http://storage.local/test.txt",
        case_id=1,
        content="Text content",
        language="en"
    )
    
    document = await document_crud.create(db_session, document_in, uploaded_by_user_id=1)
    
    assert document.id is not None
    assert document.page_count is None


@pytest.mark.asyncio
async def test_retrieve_document_with_ocr_metadata(db_session: AsyncSession):
    """Test retrieving a document and verifying OCR metadata persistence."""
    document_in = DocumentCreate(
        filename="legal_brief.pdf",
        s3_url="http://storage.local/legal_brief.pdf",
        case_id=1,
        content="This is a legal brief with multiple pages of content.",
        language="en",
        page_count=12,
        classification="legal_brief"
    )
    
    created_doc = await document_crud.create(db_session, document_in, uploaded_by_user_id=1)
    retrieved_doc = await document_crud.get(db_session, created_doc.id)
    
    assert retrieved_doc is not None
    assert retrieved_doc.content == "This is a legal brief with multiple pages of content."
    assert retrieved_doc.language == "en"
    assert retrieved_doc.page_count == 12


@pytest.mark.asyncio
async def test_update_document_page_count(db_session: AsyncSession):
    """Test updating document page_count after re-processing."""
    from app.schemas.document import DocumentUpdate
    
    document_in = DocumentCreate(
        filename="contract.pdf",
        s3_url="http://storage.local/contract.pdf",
        case_id=1,
        content="Initial content",
        language="en",
        page_count=3
    )
    
    document = await document_crud.create(db_session, document_in, uploaded_by_user_id=1)
    
    update_data = DocumentUpdate(
        filename="contract.pdf",
        s3_url="http://storage.local/contract.pdf",
        case_id=1,
        content="Updated content with more pages",
        page_count=7
    )
    
    updated_doc = await document_crud.update(db_session, document.id, update_data)
    
    assert updated_doc.page_count == 7
    assert updated_doc.content == "Updated content with more pages"


@pytest.mark.asyncio
async def test_full_text_search_with_page_count(db_session: AsyncSession):
    """Test that documents with page_count can be searched."""
    doc1 = DocumentCreate(
        filename="doc1.pdf",
        s3_url="http://storage.local/doc1.pdf",
        case_id=1,
        content="Contract for software development services",
        language="en",
        page_count=8
    )
    
    doc2 = DocumentCreate(
        filename="doc2.pdf",
        s3_url="http://storage.local/doc2.pdf",
        case_id=1,
        content="Invoice for consulting services",
        language="en",
        page_count=2
    )
    
    await document_crud.create(db_session, doc1, uploaded_by_user_id=1)
    await document_crud.create(db_session, doc2, uploaded_by_user_id=1)
    
    results = await document_crud.full_text_search(db_session, "services", case_id=1)
    
    assert len(results) == 2
    assert all(doc.page_count is not None for doc in results)


@pytest.mark.asyncio
async def test_document_with_hebrew_language(db_session: AsyncSession):
    """Test creating document with Hebrew language detection."""
    document_in = DocumentCreate(
        filename="hebrew_doc.pdf",
        s3_url="http://storage.local/hebrew_doc.pdf",
        case_id=1,
        content="תוכן בעברית",
        language="he",
        page_count=4
    )
    
    document = await document_crud.create(db_session, document_in, uploaded_by_user_id=1)
    
    assert document.language == "he"
    assert document.page_count == 4
    assert document.content == "תוכן בעברית"
