"""Dump raw position fields for a given token id or list index.

Use this to see raw fields like conditionId/outcomeIndex/negativeRisk
before attempting brute-force or trace-based redemption.
"""

from __future__ import annotations

import argparse
import json

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet


def _load_positions() -> list[dict]:
    data = fetch_data(f"https://data-api.polymarket.com/positions?user={PROXY_WALLET}")
    return data if isinstance(data, list) else []


def _sort_positions(positions: list[dict]) -> list[dict]:
    return sorted(
        positions, key=lambda p: float(p.get("currentValue") or 0), reverse=True
    )


def _find_position(sorted_positions: list[dict], position_id: str) -> dict | None:
    if position_id.isdigit() and len(position_id) <= 4:
        index = int(position_id)
        if 1 <= index <= len(sorted_positions):
            return sorted_positions[index - 1]
        return None

    for pos in sorted_positions:
        if str(pos.get("asset") or "") == str(position_id):
            return pos
        if str(pos.get("conditionId") or "") == str(position_id):
            return pos
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a raw position payload.")
    parser.add_argument(
        "position_id",
        help="Numeric ID from get_redeemable_ids.py or token/condition id",
    )
    args = parser.parse_args()

    # Raw payloads come from the Polymarket positions API.
    positions = _load_positions()
    if not positions:
        print("No open positions")
        return

    sorted_positions = _sort_positions(positions)
    position = _find_position(sorted_positions, args.position_id)
    if not position:
        print(f"Position not found: {args.position_id}")
        return

    print("Position payload (raw):")
    print(json.dumps(position, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
