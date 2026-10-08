class ConflictError(Exception):
    """Raised when optimistic concurrency or idempotency detects a conflict."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
