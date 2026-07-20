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

    ALLOWED_TABLES = {"customers", "orders", "order_items", "products", "reviews"}
    for table_node in parsed.find_all(exp.Table):
        if table_node.name.lower() not in ALLOWED_TABLES:
            raise SecurityViolationError(f"Security violation: Table '{table_node.name}' is not in the allowlist or is a system catalog.")

    # 3. Static Join-Condition Validation
    for join_node in parsed.find_all(exp.Join):
        on_clause = join_node.args.get("on")
        if not on_clause:
            raise SecurityViolationError("Algorithmic Denial of Service Blocked: CROSS JOIN or missing ON clause detected.")
        if not any(isinstance(node, exp.EQ) for node in on_clause.walk()):
            raise SecurityViolationError("Algorithmic Denial of Service Blocked: JOIN condition lacks a strict equality (=) comparison.")

    # 4. Enforce LIMIT to prevent unbounded result set exhaustion
    limit_node = parsed.args.get("limit")
    if not limit_node:
        parsed = parsed.limit(enforce_limit)
    else:
        try:
            limit_val = int(limit_node.expression.this)
            if limit_val > enforce_limit:
                limit_node.set("expression", exp.Literal.number(enforce_limit))
        except Exception:
            limit_node.set("expression", exp.Literal.number(enforce_limit))
        
    return parsed.sql(dialect="sqlite")

if __name__ == "__main__":
    print("Testing Valid Query...")
    print(validate_and_format_sql("SELECT * FROM customers"))
    
    print("\nTesting Forbidden Query (T8 Pragma)...")
    try:
        validate_and_format_sql("PRAGMA journal_mode = WAL;")
    except Exception as e:
        print("Blocked successfully:", e)
