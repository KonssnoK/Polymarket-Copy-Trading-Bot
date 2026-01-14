"""Sell large positions script."""

from __future__ import annotations

import time

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, OrderArgs, OrderType, AssetType
from py_clob_client.order_builder.constants import SELL

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.create_clob_client import create_clob_client
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet
RETRY_LIMIT = ENV.retry_limit

SELL_PERCENTAGE = 0.8
MIN_POSITION_VALUE = 17.0


def _update_polymarket_cache(clob_client: ClobClient, token_id: str) -> None:
    try:
        print("Updating Polymarket balance cache for token...")
        clob_client.update_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id)
        )
        print("Cache updated successfully\n")
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: could not update cache: {exc}")


def _extract_order_error(response) -> str | None:
    if not response:
        return None
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        if isinstance(response.get("error"), str):
            return response.get("error")
        if isinstance(response.get("error"), dict):
            nested = response.get("error")
            if isinstance(nested.get("error"), str):
                return nested.get("error")
            if isinstance(nested.get("message"), str):
                return nested.get("message")
        if isinstance(response.get("errorMsg"), str):
            return response.get("errorMsg")
        if isinstance(response.get("message"), str):
            return response.get("message")
    return None


def _sell_position(clob_client: ClobClient, position: dict, sell_size: float) -> bool:
    remaining = sell_size
    retry = 0

    print(
        f"\nStarting to sell {sell_size:.2f} tokens ({SELL_PERCENTAGE * 100:.0f}% of position)"
    )
    print(f"Token ID: {str(position.get('asset'))[:20]}...")
    print(f"Market: {position.get('title')} - {position.get('outcome')}\n")

    _update_polymarket_cache(clob_client, position.get("asset"))

    while remaining > 0 and retry < RETRY_LIMIT:
        try:
            order_book = clob_client.get_order_book(position.get("asset"))
            bids = order_book.bids
            if not bids:
                print("No bids available in order book")
                break

            max_bid = max(bids, key=lambda bid: float(bid.price))
            max_bid_price = float(max_bid.price)
            max_bid_size = float(max_bid.size)
            print(f"Best bid: {max_bid_size} tokens @ ${max_bid_price}")

            order_amount = remaining if remaining <= max_bid_size else max_bid_size

            order_args = OrderArgs(
                token_id=str(position.get("asset") or ""),
                price=max_bid_price,
                size=order_amount,
                side=SELL,
            )

            print(f"Selling {order_amount:.2f} tokens at ${order_args.price}...")
            signed = clob_client.create_order(order_args)
            resp = clob_client.post_order(signed, OrderType.FOK)

            if resp and resp.get("success") is True:
                retry = 0
                sold_value = order_amount * order_args.price
                print(
                    f"SUCCESS: Sold {order_amount:.2f} tokens at ${order_args.price} (Total: ${sold_value:.2f})"
                )
                remaining -= order_amount
                if remaining > 0:
                    print(f"Remaining to sell: {remaining:.2f} tokens\n")
            else:
                retry += 1
                error_msg = _extract_order_error(resp)
                print(
                    f"Order failed (attempt {retry}/{RETRY_LIMIT}){f': {error_msg}' if error_msg else ''}"
                )
                if retry < RETRY_LIMIT:
                    print("Retrying...\n")
                    time.sleep(1)
        except Exception as exc:  # noqa: BLE001
            retry += 1
            print(f"Error during sell attempt {retry}/{RETRY_LIMIT}: {exc}")
            if retry < RETRY_LIMIT:
                print("Retrying...\n")
                time.sleep(1)

    if remaining > 0:
        print(f"Could not sell all tokens. Remaining: {remaining:.2f} tokens")
        return False

    print(f"Successfully sold {sell_size:.2f} tokens!")
    return True


def main() -> None:
    print("Sell Large Positions Script")
    print(f"Wallet: {PROXY_WALLET}")
    print(f"Sell percentage: {SELL_PERCENTAGE * 100:.0f}%")
    print(f"Minimum position value: ${MIN_POSITION_VALUE}\n")

    clob_client = create_clob_client()
    print("Connected to Polymarket\n")

    positions = fetch_data(
        f"https://data-api.polymarket.com/positions?user={PROXY_WALLET}"
    ) or []
    print(f"Found {len(positions)} position(s)\n")

    large_positions = [p for p in positions if float(p.get("currentValue") or 0) > MIN_POSITION_VALUE]

    if not large_positions:
        print(f"No positions larger than ${MIN_POSITION_VALUE} found.")
        return

    large_positions.sort(key=lambda p: float(p.get("currentValue") or 0), reverse=True)

    print(f"Found {len(large_positions)} large position(s):\n")
    for pos in large_positions:
        print(f"  - {pos.get('title') or 'Unknown'} [{pos.get('outcome')}]")
        print(
            f"    Current: ${float(pos.get('currentValue') or 0):.2f} ({float(pos.get('size') or 0):.2f} shares)"
        )
        print(
            f"    Will sell: {(float(pos.get('size') or 0) * SELL_PERCENTAGE):.2f} shares ({SELL_PERCENTAGE * 100:.0f}%)"
        )
        print("")

    success_count = 0
    failure_count = 0
    total_sold = 0.0

    for idx, position in enumerate(large_positions, start=1):
        sell_size = int(float(position.get("size") or 0) * SELL_PERCENTAGE)
        print(f"\nPosition {idx}/{len(large_positions)}")
        print(f"Market: {position.get('title') or 'Unknown'}")
        print(f"Outcome: {position.get('outcome') or 'Unknown'}")
        print(f"Position size: {float(position.get('size') or 0):.2f} tokens")
        print(f"Average price: ${float(position.get('avgPrice') or 0):.4f}")
        print(f"Current value: ${float(position.get('currentValue') or 0):.2f}")
        print(
            f"PnL: ${float(position.get('cashPnl') or 0):.2f} ({float(position.get('percentPnl') or 0):.2f}%)"
        )

        if sell_size < 1.0:
            print(
                f"Skipping: Sell size ({sell_size:.2f} tokens) is below minimum (1.0 token)"
            )
            failure_count += 1
            continue

        success = _sell_position(clob_client, position, sell_size)
        if success:
            success_count += 1
            total_sold += sell_size
        else:
            failure_count += 1

        if idx < len(large_positions):
            print("\nWaiting 2 seconds before next sale...\n")
            time.sleep(2)

    print("\nSUMMARY")
    print(f"Successful sales: {success_count}/{len(large_positions)}")
    print(f"Failed sales: {failure_count}/{len(large_positions)}")
    print(f"Total tokens sold: {total_sold:.2f}")
    print("\nScript completed!")


if __name__ == "__main__":
    main()
