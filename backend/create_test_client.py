"""
Quick script to create a test client in the database
Run this if you get "client_id not found" errors when creating cases
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_maker
from app.db.models.client import Client

async def create_test_client():
    async with async_session_maker() as db:
        # Check if client already exists
        existing = await db.get(Client, 1)
        if existing:
            print(f"Client already exists: {existing.name}")
            return
        
        # Create test client
        client = Client(
            name="Test Client",
            contact_person="John Doe",
            contact_email="john@example.com",
            phone_number="+1234567890",
            address="123 Test Street"
        )
        db.add(client)
        await db.commit()
        await db.refresh(client)
        print(f"Created test client with ID: {client.id}")

if __name__ == "__main__":
    asyncio.run(create_test_client())
