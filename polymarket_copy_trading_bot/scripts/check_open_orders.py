"""List open CLOB orders for the current API key."""

from __future__ import annotations

import argparse
import json

from py_clob_client.clob_types import OpenOrderParams

from polymarket_copy_trading_bot.utils.create_clob_client import create_clob_client


def _format_order(order: dict) -> str:
    order_id = order.get("id") or ""
    market = order.get("market") or ""
    token_id = order.get("asset_id") or ""
    side = order.get("side") or ""
    price = order.get("price") or ""
    size = order.get("size") or ""
    status = order.get("status") or ""
    return f"{order_id:<36} {side:<4} {price:<8} {size:<10} {status:<8} {market:<12} {token_id}"


def main() -> None:
    parser = argparse.ArgumentParser(description="List or cancel open orders.")
    parser.add_argument("--market", help="Filter by market/condition id")
    parser.add_argument("--token-id", help="Filter by token/asset id")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON")
    parser.add_argument(
        "--cancel",
        nargs="+",
        help="Cancel specific order IDs",
    )
    parser.add_argument(
        "--cancel-all",
        action="store_true",
        help="Cancel all open orders",
    )
    parser.add_argument(
        "--cancel-filtered",
        action="store_true",
        help="Cancel orders matching --market/--token-id filters",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts",
    )
    args = parser.parse_args()

    clob_client = create_clob_client()
    params = None
    if args.market or args.token_id:
        params = OpenOrderParams(market=args.market, asset_id=args.token_id)

    if args.cancel_all:
        if not args.yes:
            confirm = input("Cancel ALL open orders? Type 'yes' to confirm: ").strip().lower()
            if confirm != "yes":
                print("Cancelled.")
                return
        resp = clob_client.cancel_all()
        print(resp)
        return

    if args.cancel:
        if not args.yes:
            confirm = input(
                f"Cancel {len(args.cancel)} order(s)? Type 'yes' to confirm: "
            ).strip().lower()
            if confirm != "yes":
                print("Cancelled.")
                return
        resp = clob_client.cancel_orders(args.cancel)
        print(resp)
        return

    if args.cancel_filtered:
        orders = clob_client.get_orders(params)
        if not orders:
            print("No open orders to cancel.")
            return
        order_ids = [order.get("id") for order in orders if order.get("id")]
        if not order_ids:
            print("No cancellable order IDs found.")
            return
        if not args.yes:
            confirm = input(
                f"Cancel {len(order_ids)} filtered order(s)? Type 'yes' to confirm: "
            ).strip().lower()
            if confirm != "yes":
                print("Cancelled.")
                return
        resp = clob_client.cancel_orders(order_ids)
        print(resp)
        return

    orders = clob_client.get_orders(params)
    if args.raw:
        print(json.dumps(orders, indent=2))
        return

    if not orders:
        print("No open orders.")
        return

    print(f"Open orders: {len(orders)}\n")
    print("Order ID                             Side Price    Size       Status   Market       Token ID")
    print("-" * 110)
    for order in orders:
        print(_format_order(order))


if __name__ == "__main__":
    main()
