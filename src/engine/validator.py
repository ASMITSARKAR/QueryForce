import sqlglot
from sqlglot import exp
from src.engine.errors import SecurityViolationError

def validate_and_format_sql(sql: str, enforce_limit: int = 500) -> str:
    """
    Parses the SQL using sqlglot to ensure it is syntactically valid SQLite.
    Walks the Abstract Syntax Tree (AST) to block all writing/modifying commands.
    Implements the T8 fix to block dangerous PRAGMA statements.
    Injects a LIMIT if missing to prevent terminal flooding.
    """
    try:
        # Parse SQL specifically for SQLite dialect
        parsed = sqlglot.parse_one(sql, read="sqlite")
    except Exception as e:
        raise SecurityViolationError(f"Failed to parse SQL: {str(e)}")

    # 1. Block DDL, DML, and PRAGMA
    # sqlglot expression types that indicate modification or administration
    forbidden_types = (
        exp.Drop,
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.AlterTable,
        exp.Pragma,  # T8 Fix: Strict PRAGMA prevention
        exp.Commit,
        exp.Rollback,
        exp.Transaction
    )

    forbidden_nodes = list(parsed.find_all(forbidden_types))
    if forbidden_nodes:
        offending_type = forbidden_nodes[0].__class__.__name__
        raise SecurityViolationError(f"Security violation: Found forbidden command type '{offending_type}'. Only SELECT is allowed.")

    # 2. Enforce LIMIT to prevent flooding the terminal or memory
    if not parsed.args.get("limit"):
        parsed = parsed.limit(enforce_limit)
        
    return parsed.sql(dialect="sqlite")

if __name__ == "__main__":
    print("Testing Valid Query...")
    print(validate_and_format_sql("SELECT * FROM customers"))
    
    print("\nTesting Forbidden Query (T8 Pragma)...")
    try:
        validate_and_format_sql("PRAGMA journal_mode = WAL;")
    except Exception as e:
        print("Blocked successfully:", e)
