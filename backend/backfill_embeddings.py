import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models.document import Document, DocumentChunk
from app.services.llm import llm_service

async def run():
    print("Starting vector backfill...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Document))
        docs = result.scalars().all()
        for doc in docs:
            if not doc.content or doc.content == "Processing text...":
                continue
            
            # Check if chunks exist
            chunks_result = await db.execute(select(DocumentChunk).filter(DocumentChunk.document_id == doc.id))
            if chunks_result.scalars().first():
                print(f"Document {doc.id} already has vector chunks. Skipping.")
                continue 
                
            print(f"Generating embeddings for Document {doc.id}...")
            full_text = doc.content
            chunk_size = 2000
            chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]

            for index, text_chunk in enumerate(chunks):
                try:
                    vector_array = await llm_service.generate_embedding(text_chunk)
                    db_chunk = DocumentChunk(
                        document_id=doc.id,
                        chunk_index=index,
                        text_content=text_chunk,
                        embedding=vector_array
                    )
                    db.add(db_chunk)
                except Exception as e:
                    print(f"Failed to generate embedding for doc {doc.id} chunk {index}: {e}")
            await db.commit()
            print(f"Finished generating vector chunks for Document {doc.id}")
            
    print("Vector embedding backfill complete.")

if __name__ == "__main__":
    asyncio.run(run())
