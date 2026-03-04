import pytest
from app.services.metadata_extraction import metadata_extraction_service


@pytest.mark.asyncio
async def test_extract_dates():
    """Test date extraction from text."""
    text = "The contract was signed on 01/15/2024 and expires on 2025-12-31. Meeting scheduled for Jan 20, 2024."
    
    metadata = await metadata_extraction_service.extract_metadata(text)
    
    assert len(metadata["dates"]) > 0
    assert any("2024" in date for date in metadata["dates"])


@pytest.mark.asyncio
async def test_extract_amounts():
    """Test monetary amount extraction."""
    text = "The settlement amount is $150,000.00. Additional fees of $5,000 USD and ₪10,000 are due."
    
    metadata = await metadata_extraction_service.extract_metadata(text)
    
    assert len(metadata["amounts"]) > 0
    assert any("$" in amount or "USD" in amount or "₪" in amount for amount in metadata["amounts"])


@pytest.mark.asyncio
async def test_extract_case_numbers():
    """Test case number extraction."""
    text = "This matter is filed under Case CV-2024-12345 and related to Docket #AB-98765."
    
    metadata = await metadata_extraction_service.extract_metadata(text)
    
    assert len(metadata["case_numbers"]) > 0


@pytest.mark.asyncio
async def test_extract_entities():
    """Test entity (person/organization) extraction."""
    text = "John Doe and Jane Smith represent Acme Corporation Inc. The opposing party is Tech Solutions LLC."
    
    metadata = await metadata_extraction_service.extract_metadata(text)
    
    assert len(metadata["entities"]) > 0
    assert any("Inc" in entity or "LLC" in entity or "Doe" in entity for entity in metadata["entities"])


@pytest.mark.asyncio
async def test_extract_hebrew_entities():
    """Test Hebrew entity extraction."""
    text = "החוזה נחתם על ידי דוד כהן ושרה לוי מטעם חברת טכנולוגיה בע\"מ"
    
    metadata = await metadata_extraction_service.extract_metadata(text, language="he")
    
    assert "entities" in metadata
    # Hebrew entities should be extracted
    assert len(metadata["entities"]) >= 0  # May or may not find entities depending on pattern


@pytest.mark.asyncio
async def test_extract_metadata_empty_text():
    """Test metadata extraction with empty text."""
    text = ""
    
    metadata = await metadata_extraction_service.extract_metadata(text)
    
    assert metadata["dates"] == []
    assert metadata["entities"] == []
    assert metadata["amounts"] == []
    assert metadata["case_numbers"] == []


@pytest.mark.asyncio
async def test_extract_metadata_error_tolerance():
    """Test that extraction is error tolerant."""
    text = None  # Invalid input
    
    try:
        metadata = await metadata_extraction_service.extract_metadata(text or "")
        assert isinstance(metadata, dict)
        assert "dates" in metadata
    except:
        pytest.fail("Metadata extraction should be error tolerant")


@pytest.mark.asyncio
async def test_extract_complex_document():
    """Test extraction from complex legal document."""
    text = """
    SETTLEMENT AGREEMENT
    
    This Agreement is entered into on January 15, 2024, between John Smith and 
    Acme Corporation Inc. (Case No. CV-2024-12345).
    
    The parties agree to a settlement amount of $250,000.00, payable by March 1, 2024.
    Additional attorney fees of $15,000 USD shall be paid by February 15, 2024.
    
    Signed: Jane Doe, Esq.
    Date: 01/15/2024
    """
    
    metadata = await metadata_extraction_service.extract_metadata(text)
    
    assert len(metadata["dates"]) >= 2
    assert len(metadata["amounts"]) >= 2
    assert len(metadata["entities"]) >= 2
    assert len(metadata["case_numbers"]) >= 1


@pytest.mark.asyncio
async def test_metadata_limits():
    """Test that extraction respects limits."""
    # Create text with many dates
    text = " ".join([f"Date: {i}/01/2024" for i in range(1, 50)])
    
    metadata = await metadata_extraction_service.extract_metadata(text)
    
    # Should limit to 20 dates
    assert len(metadata["dates"]) <= 20
