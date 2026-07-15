class CroquiEngineError(Exception):
    """Base exception for local processing failures."""


class UnsupportedPdfError(CroquiEngineError):
    """Raised when the PDF cannot be opened locally."""


class PermissionDeniedError(CroquiEngineError):
    """Raised when a user role cannot execute an action."""
