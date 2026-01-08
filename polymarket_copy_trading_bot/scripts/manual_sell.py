"""Manual sell script."""

from __future__ import annotations

import time
from typing import Any

import requests
from web3 import Web3

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, OrderArgs, OrderType, AssetType
from py_clob_client.order_builder.constants import SELL

from polymarket_copy_trading_bot.config.env import ENV

PROXY_WALLET = ENV.proxy_wallet
PRIVATE_KEY = ENV.private_key
CLOB_HTTP_URL = ENV.clob_http_url
RPC_URL = ENV.rpc_url
POLYGON_CHAIN_ID = 137
RETRY_LIMIT = ENV.retry_limit

MARKET_SEARCH_QUERY = "Maduro out in 2025"
SELL_PERCENTAGE = 0.7


def _is_gnosis_safe(address: str, web3: Web3) -> bool:
    code = web3.eth.get_code(address)
    return code not in (b"", b"0x") and len(code) > 0


def _create_clob_client(web3: Web3) -> ClobClient:
    is_proxy_safe = _is_gnosis_safe(PROXY_WALLET, web3)
    signature_type = 2 if is_proxy_safe else 0

    client = ClobClient(
        CLOB_HTTP_URL,
        chain_id=POLYGON_CHAIN_ID,
        key=PRIVATE_KEY,
        signature_type=signature_type,
        funder=PROXY_WALLET,
    )

    client.set_api_creds(client.create_or_derive_api_creds())
    return client


def _fetch_positions() -> list[dict]:
    url = f"https://data-api.polymarket.com/positions?user={PROXY_WALLET}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def _find_matching_position(positions: list[dict], search_query: str) -> dict | None:
    for pos in positions:
        title = (pos.get("title") or "").lower()
        if search_query.lower() in title:
            return pos
    return None


def _update_polymarket_cache(clob_client: ClobClient, token_id: str) -> None:
    try:
        print("Updating Polymarket balance cache for token...")
        clob_client.update_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id)
        )
        print("Cache updated successfully\n")
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: Could not update cache: {exc}")


def _sell_position(clob_client: ClobClient, position: dict, sell_size: float) -> None:
    remaining = sell_size
    retry = 0

    print(
        f"\nStarting to sell {sell_size:.2f} tokens ({SELL_PERCENTAGE * 100:.0f}% of position)"
    )
    print(f"Token ID: {position.get('asset')}")
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
            print(f"Best bid: {max_bid.size} tokens @ ${max_bid.price}")

            bid_size = float(max_bid.size)
            order_amount = remaining if remaining <= bid_size else bid_size

            order_args = OrderArgs(
                token_id=str(position.get("asset") or ""),
                price=float(max_bid.price),
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
                print(f"Order failed (attempt {retry}/{RETRY_LIMIT})")
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
    else:
        print(f"Successfully sold {sell_size:.2f} tokens!")


def main() -> None:
    print("Manual Sell Script")
    print(f"Wallet: {PROXY_WALLET}")
    print(f"Searching for: '{MARKET_SEARCH_QUERY}'")
    print(f"Sell percentage: {SELL_PERCENTAGE * 100:.0f}%\n")

    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    clob_client = _create_clob_client(web3)
    print("Connected to Polymarket\n")

    positions = _fetch_positions()
    print(f"Found {len(positions)} position(s)\n")

    position = _find_matching_position(positions, MARKET_SEARCH_QUERY)
    if not position:
        print(f"Position '{MARKET_SEARCH_QUERY}' not found!")
        print("\nAvailable positions:")
        for idx, pos in enumerate(positions, start=1):
            print(f"{idx}. {pos.get('title')} - {pos.get('outcome')} ({pos.get('size'):.2f} tokens)")
        raise SystemExit(1)

    print("Position found!")
    print(f"Market: {position.get('title')}")
    print(f"Outcome: {position.get('outcome')}")
    print(f"Position size: {position.get('size'):.2f} tokens")
    print(f"Average price: ${position.get('avgPrice'):.4f}")
    print(f"Current value: ${position.get('currentValue'):.2f}")

    sell_size = float(position.get("size") or 0) * SELL_PERCENTAGE
    if sell_size < 1.0:
        print(f"Sell size ({sell_size:.2f} tokens) is below minimum (1.0 token)")
        raise SystemExit(1)

    _sell_position(clob_client, position, sell_size)


if __name__ == "__main__":
    main()
