import asyncio
import traceback
from sqlalchemy import text
from app.db.session import engine
from app.workers.document_tasks import generate_embedding_task, finalize_document_task

async def main():
    async with engine.connect() as conn:
        res = await conn.execute(text('SELECT id FROM document_chunks WHERE document_id = 29'))
        chunk = res.first()
        if not chunk:
            print("No chunks found.")
            return
            
        chunk_id = chunk[0]
        
        with open("/app/backend/embed_error.log", "w") as f:
            f.write(f"Testing generate_embedding_task manually locally for chunk {chunk_id}...\n")
            try:
                generate_embedding_task(chunk_id)
                f.write("Embedding generated successfully!\n")
            except Exception as e:
                f.write(f"FAILED EMBEDDING:\n{traceback.format_exc()}\n")
                
            f.write("\nTesting finalize_document_task manually...\n")
            try:
                # Mock results for finalize
                finalize_document_task([None], 29, 0)
                f.write("Finalize task succeeded!\n")
            except Exception as e:
                f.write(f"FAILED FINALIZE:\n{traceback.format_exc()}\n")

if __name__ == "__main__":
    asyncio.run(main())
