class ValidationError(Exception):
    """Raised when client input is invalid. Rendered as HTTP 400."""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist. Rendered as HTTP 404."""


class ConflictError(Exception):
    """Raised when a request conflicts with existing state. Rendered as HTTP 409."""
