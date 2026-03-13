import asyncio
import sys
import os
import logging

logging.basicConfig(level=logging.INFO)

sys.path.append("/app/backend")

from app.db.session import AsyncSessionLocal
from app.services.audit import log_audit, verify_audit_chain
from sqlalchemy import text

async def main():
    print("Testing Audit Logger...")
    async with AsyncSessionLocal() as db:
        # Get first valid organization
        result = await db.execute(text("SELECT id FROM organizations LIMIT 1"))
        org_id_row = result.fetchone()
        org_id = org_id_row[0] if org_id_row else None
        
        print(f"Using Organization ID: {org_id}")
        
        # 1. Clear out any existing logs for this org
        if org_id:
            await db.execute(text(f"DELETE FROM audit_logs WHERE organization_id = {org_id}"))
        else:
            await db.execute(text("DELETE FROM audit_logs WHERE organization_id IS NULL"))
        await db.commit()
        
        # 2. Add some logs
        print("Adding log 1...")
        log1 = await log_audit(
            db=db,
            event_type="test_event_1",
            organization_id=org_id,
            user_id=1,
            resource_type="document",
            resource_id="doc-123",
            http_method="POST",
            path="/v1/documents",
            status_code=201
        )
        print(f"Log 1 Created: ID={log1.id}, PrevHash={log1.previous_hash}, Hash={log1.hash}")
        
        print("Adding log 2...")
        log2 = await log_audit(
            db=db,
            event_type="test_event_2",
            organization_id=org_id,
            user_id=1,
            resource_type="document",
            resource_id="doc-124",
            http_method="DELETE",
            path="/v1/documents/doc-124",
            status_code=204
        )
        print(f"Log 2 Created: ID={log2.id}, PrevHash={log2.previous_hash}, Hash={log2.hash}")
        
        # 3. Verify Chain
        print("Verifying Chain...")
        is_valid = await verify_audit_chain(db, org_id)
        print(f"CHAIN VALID: {is_valid}")
        
        if not is_valid:
            sys.exit(1)
            
        print("SUCCESS! Tamper-resistant chaining works correctly.")

if __name__ == "__main__":
    asyncio.run(main())
