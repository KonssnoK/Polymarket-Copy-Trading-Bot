"""Application-specific error types."""

from __future__ import annotations


class AppError(Exception):
    """Base class for application errors."""


class ConfigurationError(AppError):
    """Raised when configuration is invalid or missing."""


class DatabaseError(AppError):
    """Raised when database operations fail."""


class TradingError(AppError):
    """Raised when trading operations fail."""


class InsufficientFundsError(TradingError):
    """Raised when balance or allowance is insufficient."""
