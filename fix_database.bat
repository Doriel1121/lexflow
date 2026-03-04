@echo off
echo ========================================
echo Fixing Database Schema
echo ========================================
echo.
echo Adding organization_id columns to all tables...
echo.

docker exec -i ai-lawyer-db-1 psql -U admin -d lexflow_db < fix_database.sql

if %errorlevel% equ 0 (
    echo.
    echo ✅ Database schema updated successfully!
    echo.
    echo Now restart the backend:
    echo   docker-compose restart backend
    echo.
) else (
    echo.
    echo ❌ Failed to update database
    echo.
    echo Make sure Docker is running:
    echo   docker ps
    echo.
)

pause
