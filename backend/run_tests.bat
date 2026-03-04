@echo off
REM Test Runner Script for LexFlow Backend (Windows)

echo ========================================
echo    LexFlow Test Suite
echo ========================================
echo.

REM Check if pytest is installed
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pytest not found. Installing...
    pip install pytest pytest-asyncio pytest-cov
)

echo Running all tests...
echo.

REM Run all tests
python -m pytest tests\ -v --tb=short

if errorlevel 1 (
    echo.
    echo [FAILED] Some tests failed
    exit /b 1
) else (
    echo.
    echo [SUCCESS] All tests passed!
)

echo.
echo Running tests with coverage...
python -m pytest tests\ --cov=app --cov-report=term-missing --cov-report=html

echo.
echo ========================================
echo Test run complete!
echo Coverage report: htmlcov\index.html
echo ========================================
