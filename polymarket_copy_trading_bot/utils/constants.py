"""Shared constants for trading and database fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradingConstants:
    min_order_size_usd: float = 1.0
    min_order_size_tokens: float = 1.0
    max_price_slippage: float = 0.05


TRADING_CONSTANTS = TradingConstants()


@dataclass(frozen=True)
class DbFields:
    bot_executed: str = "bot"
    bot_executed_time: str = "botExcutedTime"
    my_bought_size: str = "myBoughtSize"
    side_buy: str = "BUY"


DB_FIELDS = DbFields()
