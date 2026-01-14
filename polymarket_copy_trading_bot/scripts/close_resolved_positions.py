"""Close resolved positions based on price thresholds."""

from __future__ import annotations

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
ZERO_THRESHOLD = 0.0001
RESOLVED_HIGH = 0.99
RESOLVED_LOW = 0.01


def _update_polymarket_cache(clob_client: ClobClient, token_id: str) -> None:
    try:
        clob_client.update_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id)
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: failed to refresh balance cache for {token_id}: {exc}")


def _sell_entire_position(clob_client: ClobClient, position: dict) -> dict:
    remaining = float(position.get("size") or 0)
    attempts = 0
    sold_tokens = 0.0
    proceeds_usd = 0.0

    if remaining < MIN_SELL_TOKENS:
        print(
            f"  Position size {remaining:.4f} < {MIN_SELL_TOKENS} token minimum, skipping"
        )
        return {"soldTokens": 0.0, "proceedsUsd": 0.0, "remainingTokens": remaining}

    _update_polymarket_cache(clob_client, position.get("asset"))

    while remaining >= MIN_SELL_TOKENS and attempts < RETRY_LIMIT:
        order_book = clob_client.get_order_book(position.get("asset"))
        bids = order_book.bids
        if not bids:
            print("  Order book has no bids; liquidity unavailable")
            break

        best_bid = max(bids, key=lambda bid: float(bid.price))
        bid_size = float(best_bid.size)
        bid_price = float(best_bid.price)

        if bid_size < MIN_SELL_TOKENS:
            print(f"  Best bid only for {bid_size:.2f} tokens (< {MIN_SELL_TOKENS})")
            break

        sell_amount = min(remaining, bid_size)
        if sell_amount < MIN_SELL_TOKENS:
            print(f"  Remaining amount {sell_amount:.4f} below minimum sell size")
            break

        order_args = OrderArgs(
            token_id=str(position.get("asset") or ""),
            price=bid_price,
            size=sell_amount,
            side=SELL,
        )

        try:
            signed = clob_client.create_order(order_args)
            resp = clob_client.post_order(signed, OrderType.FOK)
            if resp and resp.get("success") is True:
                trade_value = sell_amount * bid_price
                sold_tokens += sell_amount
                proceeds_usd += trade_value
                remaining -= sell_amount
                attempts = 0
                print(
                    f"  Sold {sell_amount:.2f} tokens @ ${bid_price:.3f} (~${trade_value:.2f})"
                )
            else:
                attempts += 1
                error_message = extract_error_message(resp)
                if is_insufficient_balance_or_allowance_error(error_message):
                    print(
                        f"  Order rejected: {error_message or 'balance/allowance issue'}"
                    )
                    break
                print(
                    f"  Sell attempt {attempts}/{RETRY_LIMIT} failed"
                    + (f" - {error_message}" if error_message else "")
                )
        except Exception as exc:  # noqa: BLE001
            attempts += 1
            print(f"  Sell attempt {attempts}/{RETRY_LIMIT} threw error: {exc}")

    if remaining >= MIN_SELL_TOKENS:
        print(f"  Remaining unsold: {remaining:.2f} tokens")
    elif remaining > 0:
        print(f"  Residual dust < {MIN_SELL_TOKENS} token left ({remaining:.4f})")

    return {
        "soldTokens": sold_tokens,
        "proceedsUsd": proceeds_usd,
        "remainingTokens": remaining,
    }


def _load_positions(address: str) -> list[dict]:
    data = fetch_data(f"https://data-api.polymarket.com/positions?user={address}")
    positions = data if isinstance(data, list) else []
    return [p for p in positions if float(p.get("size") or 0) > ZERO_THRESHOLD]


def _log_position_header(position: dict, index: int, total: int) -> None:
    status = "WIN" if float(position.get("curPrice") or 0) >= RESOLVED_HIGH else "LOSS"
    title = position.get("title") or position.get("slug") or position.get("asset")
    print(f"\n{index + 1}/{total} - {status} | {title}")
    if position.get("outcome"):
        print(f"  Outcome: {position.get('outcome')}")
    print(
        f"  Size: {float(position.get('size') or 0):.2f} tokens @ avg ${float(position.get('avgPrice') or 0):.3f}"
    )
    print(
        f"  Current price: ${float(position.get('curPrice') or 0):.4f} (Est. value: ${float(position.get('currentValue') or 0):.2f})"
    )
    if position.get("redeemable"):
        print("  Market is redeemable; can be redeemed directly")


def main() -> None:
    print("Closing resolved positions")
    print(f"Wallet: {PROXY_WALLET}")
    print(f"Win threshold: price >= ${RESOLVED_HIGH}")
    print(f"Loss threshold: price <= ${RESOLVED_LOW}")

    clob_client = create_clob_client()
    print("Connected to Polymarket CLOB")

    all_positions = _load_positions(PROXY_WALLET)
    if not all_positions:
        print("No open positions detected for proxy wallet.")
        return

    resolved_positions = [
        p
        for p in all_positions
        if float(p.get("curPrice") or 0) >= RESOLVED_HIGH
        or float(p.get("curPrice") or 0) <= RESOLVED_LOW
    ]
    active_positions = [
        p
        for p in all_positions
        if RESOLVED_LOW < float(p.get("curPrice") or 0) < RESOLVED_HIGH
    ]

    print("\nPosition statistics:")
    print(f"  Total positions: {len(all_positions)}")
    print(f"  Resolved (will be closed): {len(resolved_positions)}")
    print(f"  Active (not touching): {len(active_positions)}")

    if active_positions:
        print("\nACTIVE POSITIONS (NOT TOUCHING):")
        for idx, pos in enumerate(active_positions, start=1):
            title = pos.get("title") or pos.get("slug") or "Unknown"
            print(f"  {idx}. {title}")
            print(f"     Outcome: {pos.get('outcome') or 'N/A'}")
            print(f"     Size: {float(pos.get('size') or 0):.2f} tokens")
            print(f"     Current price: ${float(pos.get('curPrice') or 0):.4f}")
            print(f"     Value: ${float(pos.get('currentValue') or 0):.2f}")

    if not resolved_positions:
        print("\nAll positions are still active. Nothing to close.")
        return

    print(f"\nClosing {len(resolved_positions)} resolved positions...")

    total_tokens = 0.0
    total_proceeds = 0.0

    for idx, position in enumerate(resolved_positions):
        _log_position_header(position, idx, len(resolved_positions))
        try:
            result = _sell_entire_position(clob_client, position)
            total_tokens += float(result.get("soldTokens") or 0)
            total_proceeds += float(result.get("proceedsUsd") or 0)
        except Exception as exc:  # noqa: BLE001
            print(f"  Failed to close position due to unexpected error: {exc}")

    print("\nSummary of closing resolved positions")
    print(f"Markets processed: {len(resolved_positions)}")
    print(f"Tokens sold: {total_tokens:.2f}")
    print(f"USDC received (approximately): ${total_proceeds:.2f}")


if __name__ == "__main__":
    main()
