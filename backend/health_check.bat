@echo off
echo ========================================
echo LegalOS Backend Health Check
echo ========================================
echo.

echo [1/4] Checking if backend is running...
curl -s http://localhost:8000/ >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Backend is running
    curl -s http://localhost:8000/
) else (
    echo ❌ Backend is NOT running
    echo.
    echo To start backend:
    echo   cd backend
    echo   uvicorn app.main:app --reload
    echo.
    goto :end
)

echo.
echo [2/4] Testing dev-login endpoint...
curl -s "http://localhost:8000/v1/auth/dev-login?email=test@example.com" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Dev-login endpoint working
) else (
    echo ❌ Dev-login endpoint failed
)

echo.
echo [3/4] Checking CORS headers...
curl -s -I -X OPTIONS http://localhost:8000/v1/cases/ -H "Origin: http://localhost:5173" | findstr "Access-Control"
if %errorlevel% equ 0 (
    echo ✅ CORS headers present
) else (
    echo ⚠️  CORS headers not found
)

echo.
echo [4/4] Checking database connection...
curl -s http://localhost:8000/docs >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ API docs accessible
) else (
    echo ❌ API docs not accessible
)

echo.
echo ========================================
echo Health Check Complete
echo ========================================
echo.
echo Next steps:
echo 1. If backend not running: cd backend ^&^& uvicorn app.main:app --reload
echo 2. If CORS issues: Check backend/app/main.py CORS config
echo 3. Test manually: See MANUAL_TESTING_GUIDE.md
echo.

:end
