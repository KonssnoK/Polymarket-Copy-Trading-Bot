"""Error helper utilities."""

from __future__ import annotations

from typing import Any, Optional


def extract_error_message(response: Any) -> Optional[str]:
    if response is None:
        return None
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        direct = response.get("error")
        if isinstance(direct, str):
            return direct
        if isinstance(direct, dict):
            nested_error = direct.get("error")
            if isinstance(nested_error, str):
                return nested_error
            nested_message = direct.get("message")
            if isinstance(nested_message, str):
                return nested_message
        if isinstance(response.get("errorMsg"), str):
            return response.get("errorMsg")
        if isinstance(response.get("message"), str):
            return response.get("message")
    return None


def is_insufficient_balance_or_allowance_error(message: Optional[str]) -> bool:
    if not message:
        return False
    lower = message.lower()
    return "not enough balance" in lower or "allowance" in lower


def format_error(error: Any) -> str:
    if isinstance(error, Exception):
        return str(error)
    if isinstance(error, str):
        return error
    return str(error)


def get_error_stack(error: Any) -> Optional[str]:
    if isinstance(error, Exception):
        return getattr(error, "__traceback__", None)
    return None