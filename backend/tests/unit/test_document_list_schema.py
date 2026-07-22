from datetime import datetime

from app.schemas.document import DocumentListItem


def test_document_list_item_excludes_heavy_content_fields():
    item = DocumentListItem(
        id=1,
        filename="contract.pdf",
        s3_url="http://storage.local/contract.pdf",
        uploaded_by_user_id=7,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        tags=[],
    )

    payload = item.model_dump()

    assert "content" not in payload
    assert "summary" not in payload
    assert "metadata" not in payload
