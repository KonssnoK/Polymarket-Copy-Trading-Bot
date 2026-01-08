"""Health check utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import requests

from polymarket_copy_trading_bot.config.db import get_db
from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data
from polymarket_copy_trading_bot.utils.get_my_balance import get_my_balance
from polymarket_copy_trading_bot.utils.logger import Logger


@dataclass
class HealthCheckStatus:
    status: str
    message: str
    balance: float | None = None


@dataclass
class HealthCheckResult:
    healthy: bool
    checks: Dict[str, HealthCheckStatus]
    timestamp: int


def perform_health_check() -> HealthCheckResult:
    checks: Dict[str, HealthCheckStatus] = {
        "database": HealthCheckStatus(status="error", message="Not checked"),
        "rpc": HealthCheckStatus(status="error", message="Not checked"),
        "balance": HealthCheckStatus(status="error", message="Not checked"),
        "polymarketApi": HealthCheckStatus(status="error", message="Not checked"),
    }

    try:
        client = get_db()
        client.admin.command("ping")
        checks["database"] = HealthCheckStatus(status="ok", message="Connected")
    except Exception as exc:  # noqa: BLE001
        checks["database"] = HealthCheckStatus(
            status="error", message=f"Connection failed: {exc}"
        )

    try:
        response = requests.post(
            ENV.rpc_url,
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            timeout=5,
        )
        if response.ok and response.json().get("result"):
            checks["rpc"] = HealthCheckStatus(status="ok", message="RPC endpoint responding")
        else:
            checks["rpc"] = HealthCheckStatus(
                status="error", message=f"HTTP {response.status_code}"
            )
    except Exception as exc:  # noqa: BLE001
        checks["rpc"] = HealthCheckStatus(status="error", message=f"RPC check failed: {exc}")

    try:
        balance = get_my_balance(ENV.proxy_wallet)
        if balance > 0:
            if balance < 10:
                checks["balance"] = HealthCheckStatus(
                    status="warning", message=f"Low balance: ${balance:.2f}", balance=balance
                )
            else:
                checks["balance"] = HealthCheckStatus(
                    status="ok", message=f"Balance: ${balance:.2f}", balance=balance
                )
        else:
            checks["balance"] = HealthCheckStatus(status="error", message="Zero balance")
    except Exception as exc:  # noqa: BLE001
        checks["balance"] = HealthCheckStatus(
            status="error", message=f"Balance check failed: {exc}"
        )

    try:
        test_url = (
            "https://data-api.polymarket.com/positions?user=0x0000000000000000000000000000000000000000"
        )
        fetch_data(test_url)
        checks["polymarketApi"] = HealthCheckStatus(status="ok", message="API responding")
    except Exception as exc:  # noqa: BLE001
        checks["polymarketApi"] = HealthCheckStatus(
            status="error", message=f"API check failed: {exc}"
        )

    healthy = (
        checks["database"].status == "ok"
        and checks["rpc"].status == "ok"
        and checks["balance"].status != "error"
        and checks["polymarketApi"].status == "ok"
    )

    return HealthCheckResult(healthy=healthy, checks=checks, timestamp=int(__import__("time").time()))


def log_health_check(result: HealthCheckResult) -> None:
    Logger.separator()
    Logger.header("HEALTH CHECK")
    Logger.info(f"Overall Status: {'Healthy' if result.healthy else 'Unhealthy'}")
    Logger.info(
        f"Database: {result.checks['database'].status.upper()} {result.checks['database'].message}"
    )
    Logger.info(
        f"RPC: {result.checks['rpc'].status.upper()} {result.checks['rpc'].message}"
    )
    Logger.info(
        f"Balance: {result.checks['balance'].status.upper()} {result.checks['balance'].message}"
    )
    Logger.info(
        f"Polymarket API: {result.checks['polymarketApi'].status.upper()} {result.checks['polymarketApi'].message}"
    )
    Logger.separator()