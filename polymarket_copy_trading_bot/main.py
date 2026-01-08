"""Main application entry point."""

from __future__ import annotations

import signal
import sys
import time

from polymarket_copy_trading_bot.config.db import close_db, connect_db
from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.services.trade_executor import stop_trade_executor, trade_executor
from polymarket_copy_trading_bot.services.trade_monitor import stop_trade_monitor, trade_monitor
from polymarket_copy_trading_bot.utils.create_clob_client import create_clob_client
from polymarket_copy_trading_bot.utils.health_check import log_health_check, perform_health_check
from polymarket_copy_trading_bot.utils.logger import Logger

USER_ADDRESSES = ENV.user_addresses
PROXY_WALLET = ENV.proxy_wallet

_is_shutting_down = False


def _graceful_shutdown(signal_name: str) -> None:
    global _is_shutting_down
    if _is_shutting_down:
        Logger.warning("Shutdown already in progress, forcing exit...")
        sys.exit(1)

    _is_shutting_down = True
    Logger.separator()
    Logger.info(f"Received {signal_name}, initiating graceful shutdown...")

    try:
        stop_trade_monitor()
        stop_trade_executor()
        Logger.info("Waiting for services to finish current operations...")
        time.sleep(2)
        close_db()
        Logger.success("Graceful shutdown completed")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        Logger.error(f"Error during shutdown: {exc}")
        sys.exit(1)


def _install_signal_handlers() -> None:
    def handler(signum, _frame):
        name = signal.Signals(signum).name
        _graceful_shutdown(name)

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, handler)


def main() -> None:
    try:
        print("\nFirst time running the bot?")
        print("  Read the guide: GETTING_STARTED.md")
        print("  Run health check: python -m polymarket_copy_trading_bot.scripts.health_check\n")

        connect_db()
        Logger.startup(USER_ADDRESSES, PROXY_WALLET)

        Logger.info("Performing initial health check...")
        health_result = perform_health_check()
        log_health_check(health_result)
        if not health_result.healthy:
            Logger.warning("Health check failed, but continuing startup...")

        Logger.info("Initializing CLOB client...")
        clob_client = create_clob_client()
        Logger.success("CLOB client ready")

        Logger.separator()
        Logger.info("Starting trade monitor...")
        trade_monitor()

        Logger.info("Starting trade executor...")
        trade_executor(clob_client)
    except Exception as exc:  # noqa: BLE001
        Logger.error(f"Fatal error during startup: {exc}")
        _graceful_shutdown("startup-error")


if __name__ == "__main__":
    _install_signal_handlers()
    main()