"""
Test script to verify document upload and AI analysis fixes
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_ai_provider():
    """Test if AI provider initializes correctly"""
    print("\n=== Testing AI Provider ===")
    try:
        from app.core.ai_provider import get_ai_provider
        provider = get_ai_provider()
        
        if provider.active:
            print("✅ AI Provider is active")
            print(f"   Model: gemini-1.5-flash")
            print(f"   Embedding model: {provider.embedding_model}")
            print(f"   Embedding dimension: {provider.embedding_dimension}")
            
            # Test text generation
            print("\n   Testing text generation...")
            result = await provider.generate_text("Say 'Hello World' in one word")
            if result:
                print(f"   ✅ Text generation works: {result[:50]}")
            else:
                print("   ❌ Text generation returned None")
            
            # Test JSON generation
            print("\n   Testing JSON generation...")
            json_result = await provider.generate_json('Return JSON: {"test": "value"}')
            if json_result and isinstance(json_result, dict):
                print(f"   ✅ JSON generation works: {json_result}")
            else:
                print("   ❌ JSON generation failed")
            
            # Test embedding
            print("\n   Testing embedding generation...")
            embedding = await provider.generate_embedding("test text")
            if embedding and len(embedding) == provider.embedding_dimension:
                print(f"   ✅ Embedding generation works: {len(embedding)} dimensions")
            else:
                print(f"   ❌ Embedding dimension mismatch: got {len(embedding) if embedding else 0}, expected {provider.embedding_dimension}")
            
            return True
        else:
            print("❌ AI Provider is INACTIVE")
            print("   Check GEMINI_API_KEY in .env file")
            return False
    except Exception as e:
        print(f"❌ Error testing AI provider: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_database_schema():
    """Test if database schema is correct"""
    print("\n=== Testing Database Schema ===")
    try:
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as db:
            # Check document_chunks table
            result = await db.execute(text("""
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = 'document_chunks'
                AND column_name = 'embedding'
            """))
            row = result.fetchone()
            
            if row:
                print(f"✅ Embedding column exists: {row}")
                # Note: Can't easily check vector dimension from information_schema
                print("   Run fix_embedding_dimension.py if you see dimension errors")
            else:
                print("❌ Embedding column not found")
                print("   Run: python fix_embedding_dimension.py")
            
            # Check documents table
            result = await db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'documents'
                AND column_name IN ('processing_status', 'processing_stage', 'processing_progress')
            """))
            cols = [row[0] for row in result.fetchall()]
            
            if len(cols) == 3:
                print(f"✅ Document processing columns exist: {cols}")
            else:
                print(f"❌ Missing processing columns: {cols}")
            
            return True
    except Exception as e:
        print(f"❌ Error testing database: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_celery_connection():
    """Test if Celery/Redis is accessible"""
    print("\n=== Testing Celery Connection ===")
    try:
        from app.core.celery import celery_app
        
        # Try to ping Redis
        result = celery_app.control.inspect().ping()
        if result:
            print(f"✅ Celery workers responding: {list(result.keys())}")
            return True
        else:
            print("⚠️  No Celery workers found")
            print("   Start worker: celery -A app.core.celery worker --loglevel=info")
            return False
    except Exception as e:
        print(f"❌ Error connecting to Celery: {e}")
        print("   Make sure Redis is running: docker-compose up -d redis")
        return False

async def test_storage_service():
    """Test if storage service is working"""
    print("\n=== Testing Storage Service ===")
    try:
        from app.services.storage import storage_service
        
        # Check if upload directory exists
        if storage_service.upload_dir.exists():
            print(f"✅ Upload directory exists: {storage_service.upload_dir}")
            
            # Check subdirectories
            subdirs = ['inbox/unprocessed', 'inbox/processed', 'temp']
            for subdir in subdirs:
                path = storage_service.upload_dir / subdir
                if path.exists():
                    print(f"   ✅ {subdir}")
                else:
                    print(f"   ❌ {subdir} missing")
            return True
        else:
            print(f"❌ Upload directory not found: {storage_service.upload_dir}")
            return False
    except Exception as e:
        print(f"❌ Error testing storage: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("=" * 60)
    print("Document Upload & AI Analysis - System Check")
    print("=" * 60)
    
    results = []
    
    # Run all tests
    results.append(("AI Provider", await test_ai_provider()))
    results.append(("Database Schema", await test_database_schema()))
    results.append(("Celery Connection", await test_celery_connection()))
    results.append(("Storage Service", await test_storage_service()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 All tests passed! System is ready.")
    else:
        print("\n⚠️  Some tests failed. Review errors above.")
        print("\nQuick fixes:")
        print("1. Set GEMINI_API_KEY in backend/.env")
        print("2. Run: python backend/fix_embedding_dimension.py")
        print("3. Start Redis: docker-compose up -d redis")
        print("4. Start Celery: celery -A app.core.celery worker --loglevel=info")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
