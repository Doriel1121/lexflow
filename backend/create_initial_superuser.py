import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.crud.user import user_crud
from app.core.security import get_password_hash
from app.schemas.user import UserCreate
from app.db.models.user import User as DBUser # For type hinting and checking existing user

async def create_initial_superuser():
    async for db in get_db(): # get_db is an async_generator, so iterate over it
        # Check if a superuser already exists
        existing_superuser = await user_crud.get_by_email(db, email="admin@example.com")
        if existing_superuser and existing_superuser.is_superuser:
            print("Superuser 'admin@example.com' already exists.")
            return

        print("Creating initial superuser...")
        superuser_data = UserCreate(
            email="admin@example.com",
            password="adminpassword",
            full_name="Admin User",
            is_superuser=True, # Ensure this is set to True
        )
        
        # Manually set is_superuser flag during creation in CRUD layer, or adjust CRUD create method
        # For simplicity, let's create it and then update the is_superuser flag.
        # However, it's better to have a dedicated create_superuser in CRUD or a flag in UserCreate.
        
        # Let's adjust the create method to accept is_superuser flag
        # For now, I'll create it and then update the flag for simplicity
        db_user = DBUser(
            email=superuser_data.email,
            hashed_password=get_password_hash(superuser_data.password),
            full_name=superuser_data.full_name,
            is_active=True,
            is_superuser=True,
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        print(f"Superuser '{db_user.email}' created successfully!")
        break # Exit after getting the session once

if __name__ == "__main__":
    # Ensure the database is running and migrations are applied before running this script.
    # You can run this script using:
    # python -m backend.create_initial_superuser.py
    # or by navigating to the backend directory and running:
    # python create_initial_superuser.py
    
    # We need to explicitly import the models to ensure Base.metadata is populated
    # This happens when the application runs, but for a standalone script,
    # we need to ensure the models are loaded.
    import app.db.models.user
    import app.db.models.client
    import app.db.models.case
    import app.db.models.document
    import app.db.models.tag
    import app.db.models.summary
    import app.db.models.audit_log

    asyncio.run(create_initial_superuser())
