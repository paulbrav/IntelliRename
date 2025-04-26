"""Custom exceptions for the IntelliRename application."""

from typing import Optional


class IntelliRenameError(Exception):
    """Base exception for all IntelliRename errors."""

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.original_exception = original_exception

    def __str__(self) -> str:
        if self.original_exception:
            return f"{super().__str__()} (Caused by: {self.original_exception})"
        return super().__str__()


class ConfigurationError(IntelliRenameError):
    """Error related to configuration loading or validation."""

    pass


class MetadataExtractionError(IntelliRenameError):
    """Error during metadata extraction from file or filename."""

    pass


class AICommunicationError(IntelliRenameError):
    """Error communicating with the AI API (e.g., network issues, API errors)."""

    pass


class AIProcessingError(IntelliRenameError):
    """Error during AI processing (e.g., unexpected response format)."""

    pass


class FileOperationError(IntelliRenameError):
    """Error related to file system operations (read, write, rename)."""

    pass


class RenamingError(FileOperationError):
    """Specific error during the file renaming process."""

    pass


class InvalidMetadataError(IntelliRenameError):
    """Indicates that extracted or provided metadata is invalid or insufficient."""

    pass
