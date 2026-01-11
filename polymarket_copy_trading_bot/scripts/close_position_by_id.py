"""Close a single position by ID (index or token id)."""

from __future__ import annotations

import argparse

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, OrderArgs, OrderType, AssetType
from py_clob_client.order_builder.constants import SELL

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.create_clob_client import create_clob_client
from polymarket_copy_trading_bot.utils.error_helpers import (
    extract_error_message,
    is_insufficient_balance_or_allowance_error,
)
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet
RETRY_LIMIT = ENV.retry_limit

MIN_SELL_TOKENS = 1.0


def _load_positions() -> list[dict]:
    positions = fetch_data(
        f"https://data-api.polymarket.com/positions?user={PROXY_WALLET}"
    )
    return positions if isinstance(positions, list) else []


def _sort_positions(positions: list[dict]) -> list[dict]:
    return sorted(
        positions, key=lambda p: float(p.get("currentValue") or 0), reverse=True
    )


def _find_position(sorted_positions: list[dict], position_id: str) -> dict | None:
    if position_id.isdigit():
        index = int(position_id)
        if 1 <= index <= len(sorted_positions):
            return sorted_positions[index - 1]
        return None

    for pos in sorted_positions:
        if pos.get("asset") == position_id:
            return pos
        if pos.get("conditionId") == position_id:
            return pos
    return None


def _update_polymarket_cache(clob_client: ClobClient, token_id: str) -> None:
    try:
        clob_client.update_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id)
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: failed to refresh balance cache for {token_id}: {exc}")


def _sell_entire_position(clob_client: ClobClient, position: dict) -> None:
    remaining = float(position.get("size") or 0)
    attempts = 0

    if remaining < MIN_SELL_TOKENS:
        print(
            f"Position size {remaining:.4f} < {MIN_SELL_TOKENS} token minimum, skipping"
        )
        return

    token_id = str(position.get("asset") or "")
    _update_polymarket_cache(clob_client, token_id)

    while remaining >= MIN_SELL_TOKENS and attempts < RETRY_LIMIT:
        order_book = clob_client.get_order_book(token_id)
        bids = order_book.bids
        if not bids:
            print("Order book has no bids; liquidity unavailable")
            break

        best_bid = max(bids, key=lambda bid: float(bid.price))
        bid_size = float(best_bid.size)
        bid_price = float(best_bid.price)

        if bid_size < MIN_SELL_TOKENS:
            print(f"Best bid only for {bid_size:.2f} tokens (< {MIN_SELL_TOKENS})")
            break

        sell_amount = min(remaining, bid_size)
        if sell_amount < MIN_SELL_TOKENS:
            print(f"Remaining amount {sell_amount:.4f} below minimum sell size")
            break

        order_args = OrderArgs(
            token_id=token_id,
            price=bid_price,
            size=sell_amount,
            side=SELL,
        )

        try:
            signed = clob_client.create_order(order_args)
            resp = clob_client.post_order(signed, OrderType.FOK)
            if resp and resp.get("success") is True:
                trade_value = sell_amount * bid_price
                remaining -= sell_amount
                attempts = 0
                print(
                    f"Sold {sell_amount:.2f} tokens @ ${bid_price:.3f} (~${trade_value:.2f})"
                )
            else:
                attempts += 1
                error_message = extract_error_message(resp)
                if is_insufficient_balance_or_allowance_error(error_message):
                    print(
                        f"Order rejected: {error_message or 'balance/allowance issue'}"
                    )
                    break
                print(
                    f"Sell attempt {attempts}/{RETRY_LIMIT} failed"
                    + (f" - {error_message}" if error_message else "")
                )
        except Exception as exc:  # noqa: BLE001
            attempts += 1
            print(f"Sell attempt {attempts}/{RETRY_LIMIT} threw error: {exc}")

    if remaining >= MIN_SELL_TOKENS:
        print(f"Remaining unsold: {remaining:.2f} tokens")
    elif remaining > 0:
        print(f"Residual dust < {MIN_SELL_TOKENS} token left ({remaining:.4f})")
    else:
        print("Position fully closed")


def _describe_position(position: dict) -> None:
    print(f"Token ID: {position.get('asset')}")
    print(f"Market: {position.get('title') or position.get('slug') or 'Unknown'}")
    print(f"Outcome: {position.get('outcome') or 'Unknown'}")
    print(f"Size: {float(position.get('size') or 0):.2f} tokens")
    print(f"Avg price: ${float(position.get('avgPrice') or 0):.4f}")
    print(f"Current price: ${float(position.get('curPrice') or 0):.4f}")
    print(f"Current value: ${float(position.get('currentValue') or 0):.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Close a single position by ID.")
    parser.add_argument(
        "position_id",
        help="Either the numeric ID from list_positions_lean.py or the token/condition id",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    positions = _load_positions()
    if not positions:
        print("No open positions")
        return

    sorted_positions = _sort_positions(positions)
    position = _find_position(sorted_positions, args.position_id)
    if not position:
        print(f"Position not found: {args.position_id}")
        print("Use list_positions_lean.py to see valid IDs.")
        raise SystemExit(1)

    print("Position selected:")
    _describe_position(position)

    if not args.yes:
        confirm = input("Close this position? Type 'yes' to confirm: ").strip().lower()
        if confirm != "yes":
            print("Cancelled.")
            return

    clob_client = create_clob_client()
    print("Connected to Polymarket CLOB")
    _sell_entire_position(clob_client, position)


if __name__ == "__main__":
    main()
