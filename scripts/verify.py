from src.utils import suppress_chromadb_telemetry
suppress_chromadb_telemetry()

import asyncio
import sys

from src.engine.orchestrator import execute_pipeline_with_retry
from src.engine.errors import SecurityViolationError
from src.engine.validator import validate_and_format_sql

async def run_tests():
    print("Running Day 14 E2E Test Suite...")
    
    # Test 1: Happy Path
    try:
        print("\nTest 1: Happy Path ('Count all customers')")
        result = await execute_pipeline_with_retry("Count all customers")
        print(f"[PASS] Success! SQL: {result['sql']}")
        print(f"Result: {result['results']}")
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        sys.exit(1)
        
    # Test 2: Security Block (G10 Fix)
    try:
        print("\nTest 2: Security Block ('DROP TABLE users')")
        await execute_pipeline_with_retry("DROP TABLE users")
        print("[FAIL] Failed: Query was allowed to execute!")
        sys.exit(1)
    except SecurityViolationError as e:
        print(f"[PASS] Success! Blocked correctly: {e}")
    except ValueError as e:
        print(f"[PASS] Success! Blocked by confidence filter: {e}")
    except Exception as e:
        print(f"[FAIL] Failed with wrong error type: {e}")
        sys.exit(1)
        
    # Test 3: Aggregate ORDER BY Guard (G10 - T2/T7)
    try:
        print("\nTest 3: Aggregate ORDER BY Guard ('SELECT COUNT(*) AS total FROM orders')")
        validated_sql = validate_and_format_sql("SELECT COUNT(*) AS total FROM orders")
        if "ORDER BY" in validated_sql.upper():
            print(f"[FAIL] ORDER BY was injected into aggregate query: {validated_sql}")
            sys.exit(1)
        else:
            print(f"[PASS] Success! No ORDER BY injected: {validated_sql}")
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        sys.exit(1)
        
    print("\n[PASS] All 3 tests passed!")

if __name__ == "__main__":
    asyncio.run(run_tests())
