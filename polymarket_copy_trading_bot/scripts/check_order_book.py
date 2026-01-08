"""Check CLOB order book for a token ID."""

from __future__ import annotations

import argparse

from py_clob_client.client import ClobClient

from polymarket_copy_trading_bot.config.env import ENV


def main() -> None:
    parser = argparse.ArgumentParser(description="Check CLOB order book for a token ID.")
    parser.add_argument("token_id", help="CLOB token id to query")
    args = parser.parse_args()

    client = ClobClient(ENV.clob_http_url)
    book = client.get_order_book(args.token_id)

    print("orderbook", book)

    asks = getattr(book, "asks", None)
    bids = getattr(book, "bids", None)
    if asks is None and isinstance(book, dict):
        asks = book.get("asks")
    if bids is None and isinstance(book, dict):
        bids = book.get("bids")

    ask_count = len(asks) if asks else 0
    bid_count = len(bids) if bids else 0

    print(f"Token: {args.token_id}")
    print(f"Asks: {ask_count}")
    print(f"Bids: {bid_count}")

    if asks:
        best_ask = min(
            asks,
            key=lambda item: float(getattr(item, "price", None) or item.get("price", 0)),
        )
        best_ask_price = getattr(best_ask, "price", None) or best_ask.get("price")
        best_ask_size = getattr(best_ask, "size", None) or best_ask.get("size")
        print(f"Best ask: {best_ask_size} @ {best_ask_price}")
    if bids:
        best_bid = max(
            bids,
            key=lambda item: float(getattr(item, "price", None) or item.get("price", 0)),
        )
        best_bid_price = getattr(best_bid, "price", None) or best_bid.get("price")
        best_bid_size = getattr(best_bid, "size", None) or best_bid.get("size")
        print(f"Best bid: {best_bid_size} @ {best_bid_price}")


if __name__ == "__main__":
    main()
