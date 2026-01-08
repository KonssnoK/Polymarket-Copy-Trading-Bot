"""HTTP fetch helper with retries."""

from __future__ import annotations

import time
from typing import Any

import requests

from polymarket_copy_trading_bot.config.env import ENV


def _is_network_error(error: Exception) -> bool:
    return isinstance(error, requests.RequestException)


def fetch_data(url: str) -> Any:
    retries = ENV.network_retry_limit
    timeout = ENV.request_timeout_ms / 1000.0
    retry_delay = 1.0

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            is_last_attempt = attempt == retries
            if _is_network_error(exc) and not is_last_attempt:
                delay = retry_delay * (2 ** (attempt - 1))
                print(
                    f"[WARN] Network error (attempt {attempt}/{retries}), retrying in {delay:.0f}s..."
                )
                time.sleep(delay)
                continue
            if is_last_attempt and _is_network_error(exc):
                print(f"[ERROR] Network timeout after {retries} attempts")
            raise

    return None