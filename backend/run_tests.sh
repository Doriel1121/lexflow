#!/bin/bash
# Test Runner Script for LexFlow Backend

echo "🧪 LexFlow Test Suite"
echo "===================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! python -m pytest --version &> /dev/null; then
    echo -e "${RED}❌ pytest not found. Installing...${NC}"
    pip install pytest pytest-asyncio
fi

# Run all tests
echo -e "${YELLOW}Running all tests...${NC}"
python -m pytest tests/ -v --tb=short

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi

# Run with coverage (optional)
echo ""
echo -e "${YELLOW}Running tests with coverage...${NC}"
python -m pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

echo ""
echo -e "${GREEN}✅ Test run complete!${NC}"
echo "📊 Coverage report: htmlcov/index.html"
