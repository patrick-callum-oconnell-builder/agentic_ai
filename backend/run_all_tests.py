import sys
import pytest

def main():
    # Run all tests under backend/tests (unit and integration)
    exit_code = pytest.main([
        "backend/tests/unit",
        "backend/tests/integration",
        "-v"
    ])
    sys.exit(exit_code)

if __name__ == "__main__":
    main() 