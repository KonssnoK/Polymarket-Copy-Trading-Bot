"""Position helper utilities."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.interfaces.user import UserPosition
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data
from polymarket_copy_trading_bot.utils.get_my_balance import get_my_balance


class PositionStats(Dict[str, float]):
    pass


def calculate_position_stats(positions: List[UserPosition]) -> PositionStats:
    total_value = 0.0
    initial_value = 0.0
    weighted_pnl = 0.0

    for pos in positions:
        value = float(pos.get("currentValue") or 0)
        initial = float(pos.get("initialValue") or 0)
        pnl = float(pos.get("percentPnl") or 0)
        total_value += value
        initial_value += initial
        weighted_pnl += value * pnl

    overall_pnl = weighted_pnl / total_value if total_value > 0 else 0.0
    return {
        "totalValue": total_value,
        "initialValue": initial_value,
        "weightedPnl": weighted_pnl,
        "overallPnl": overall_pnl,
    }


def fetch_user_positions_and_balance(user_address: str) -> Tuple[List[UserPosition], float]:
    positions_url = f"https://data-api.polymarket.com/positions?user={user_address}"
    positions = fetch_data(positions_url)
    positions_list = positions if isinstance(positions, list) else []
    balance = sum(float(pos.get("currentValue") or 0) for pos in positions_list)
    return positions_list, balance


def fetch_my_positions_and_balance() -> Tuple[List[UserPosition], float, float]:
    positions_url = f"https://data-api.polymarket.com/positions?user={ENV.proxy_wallet}"
    positions = fetch_data(positions_url)
    positions_list = positions if isinstance(positions, list) else []

    usdc_balance = get_my_balance(ENV.proxy_wallet)
    positions_value = sum(float(pos.get("currentValue") or 0) for pos in positions_list)
    total_balance = usdc_balance + positions_value
    return positions_list, usdc_balance, total_balance


def find_position_by_condition_id(
    positions: List[UserPosition],
    condition_id: str,
) -> UserPosition | None:
    for position in positions:
        if position.get("conditionId") == condition_id:
            return position
    return None