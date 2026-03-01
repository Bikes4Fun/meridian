"""
Simplified interfaces for Meridian services.
Just contains the ServiceResult class for consistent error handling.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ServiceResult:
    """Standard result wrapper for service operations."""

    success: bool
    data: Any = None
    error: Optional[str] = None

    @classmethod
    def success_result(cls, data: Any = None) -> "ServiceResult":
        """Create a successful result."""
        return cls(success=True, data=data)

    @classmethod
    def error_result(cls, error: str) -> "ServiceResult":
        """Create an error result."""
        return cls(success=False, error=error)
