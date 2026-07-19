class QueryExecutionError(Exception):
    """Raised when a query fails to execute due to timeout or database error."""
    pass

class SecurityViolationError(Exception):
    """Raised when the AST validator blocks a malicious or non-readonly query."""
    pass
