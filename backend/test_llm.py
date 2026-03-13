import asyncio
from sqlalchemy import text
from app.db.session import engine
from app.services.llm import llm_service

async def main():
    async with engine.connect() as conn:
        res = await conn.execute(text('SELECT id, text_content FROM document_chunks WHERE document_id = 29'))
        chunk = res.first()
        if not chunk:
            print("No chunks found.")
            return
            
        chunk_id = chunk[0]
        text_content = chunk[1]
        
    print(f"Testing llm_service.generate_embedding for chunk {chunk_id}... ({len(text_content)} chars)")
    
    try:
        vector = await llm_service.generate_embedding(text_content)
        print(f"Success! Vector length: {len(vector)}")
    except Exception as e:
        print(f"API CALL FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
