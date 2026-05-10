class DocumentError(Exception):
    """Base exception for document processing errors."""


class UnsupportedFormatError(DocumentError):
    """Raised when a file format is not supported."""


class OCRProcessingError(DocumentError):
    """Raised when OCR processing fails."""


class PipelineError(DocumentError):
    """Raised when pipeline stage execution fails."""


class ExportError(DocumentError):
    """Raised when export fails."""


class TranslationError(DocumentError):
    """Raised when translation fails."""


class ConfigError(DocumentError):
    """Raised when configuration loading fails."""


class ValidationError(DocumentError):
    """Raised when data validation fails."""
