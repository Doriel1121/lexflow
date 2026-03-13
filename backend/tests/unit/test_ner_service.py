import pytest
from app.services.ai.ner_service import NERService
from app.db.models.deadline import DeadlineType
from datetime import datetime

@pytest.fixture
def ner_service():
    return NERService()

def test_extract_english_deadlines(ner_service):
    text = "A hearing is scheduled for March 15, 2025 at 9:00 AM."
    deadlines = ner_service.extract_deadlines(text, language="en")
    
    assert len(deadlines) >= 1
    # Check if any of the deadlines matches March 15, 2025
    match = next((d for d in deadlines if d["date"].year == 2025 and d["date"].month == 3 and d["date"].day == 15), None)
    assert match is not None
    assert match["type"] == DeadlineType.HEARING

def test_multiple_dates_classification(ner_service):
    text = """
    Please file the response by 10/05/2025.
    The trial is set for November 20, 2025.
    An appeal must be submitted before Jan 10, 2026.
    """
    deadlines = ner_service.extract_deadlines(text, language="en")
    
    assert len(deadlines) >= 3
    
    types = [d["type"] for d in deadlines]
    assert DeadlineType.FILING in types or DeadlineType.RESPONSE in types
    assert DeadlineType.HEARING in types
    assert DeadlineType.APPEAL in types

def test_hebrew_date_extraction(ner_service):
    # "הדיון נקבע ל-15 במרץ 2025 בשעה 9:00"
    text = "הדיון נקבע ל-15 במרץ 2025 בשעה 9:00"
    deadlines = ner_service.extract_deadlines(text, language="he")
    
    assert len(deadlines) >= 1
    match = next((d for d in deadlines if d["date"].year == 2025 and d["date"].month == 3 and d["date"].day == 15), None)
    assert match is not None
    assert match["type"] == DeadlineType.HEARING

def test_hebrew_slash_format(ner_service):
    text = "יש להגיש את כתב ההגנה עד לתאריך 15/03/2025"
    deadlines = ner_service.extract_deadlines(text, language="he")
    
    assert len(deadlines) >= 1
    match = next((d for d in deadlines if d["date"].year == 2025 and d["date"].month == 3 and d["date"].day == 15), None)
    assert match is not None
    assert match["type"] == DeadlineType.RESPONSE or match["type"] == DeadlineType.FILING

def test_mostly_hebrew_detection(ner_service):
    text = "שלום, הדיון הוא ב-12.04.2025"
    # language="en" but should detect Hebrew
    deadlines = ner_service.extract_deadlines(text, language="en")
    assert len(deadlines) >= 1
    assert deadlines[0]["date"].month == 4
    assert deadlines[0]["date"].day == 12
