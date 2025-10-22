#!/bin/bash
# Field Trainer Test Runner
# Usage: ./run_tests.sh [fast|full]

set -e  # Exit on first failure

cd /opt

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================================================"
echo "  FIELD TRAINER TEST SUITE"
echo "======================================================================"

if [ "$1" == "full" ]; then
    echo "Running FULL test suite (includes slow tests)..."
    TESTS=(
        "test_database_integrity.py"
        "test_attribution_logic.py"
        "test_touch_sequences.py"
        "test_concurrency.py"
    )
else
    echo "Running FAST test suite (pre-commit safe)..."
    TESTS=(
        "test_database_integrity.py"
        "test_attribution_logic.py"
        "test_touch_sequences.py"
    )
fi

PASSED=0
FAILED=0
START_TIME=$(date +%s)

for test in "${TESTS[@]}"; do
    echo ""
    echo "----------------------------------------------------------------------"
    echo "Running: $test"
    echo "----------------------------------------------------------------------"
    
    if sudo python3 "$test" > /tmp/test_output.log 2>&1; then
        echo -e "${GREEN}✅ PASSED${NC}: $test"
        ((PASSED++))
    else
        echo -e "${RED}❌ FAILED${NC}: $test"
        echo "Error output:"
        tail -20 /tmp/test_output.log
        ((FAILED++))
    fi
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "======================================================================"
echo "  TEST SUMMARY"
echo "======================================================================"
echo "  Total Tests: $((PASSED + FAILED))"
echo -e "  ${GREEN}Passed: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "  ${RED}Failed: $FAILED${NC}"
else
    echo "  Failed: 0"
fi
echo "  Time: ${ELAPSED}s"
echo "======================================================================"

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}⚠️  TESTS FAILED - DO NOT COMMIT${NC}"
    exit 1
else
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    exit 0
fi
