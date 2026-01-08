"""Health check script."""

from __future__ import annotations

from polymarket_copy_trading_bot.utils.health_check import log_health_check, perform_health_check


def main() -> None:
    result = perform_health_check()
    log_health_check(result)
    if not result.healthy:
        raise SystemExit(1)


if __name__ == "__main__":
    main()