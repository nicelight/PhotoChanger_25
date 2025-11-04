"""Domain-specific exceptions for ingest pipeline."""


class IngestError(Exception):
    """Base class for ingest-related errors."""


class UnsupportedMediaError(IngestError):
    """Raised when Content-Type is not allowed."""


class PayloadTooLargeError(IngestError):
    """Raised when uploaded file exceeds configured limits."""


class ChecksumMismatchError(IngestError):
    """Raised when supplied hash does not match calculated checksum."""


class UploadReadError(IngestError):
    """Raised when streaming the upload fails."""


class ProviderTimeoutError(IngestError):
    """Raised when provider does not finish before T_sync_response."""


class ProviderExecutionError(IngestError):
    """Raised when provider driver fails before producing a result."""
