"""Print trade transaction hashes for a given position (token or condition).

Flow (debug redeem):
1) Find token/condition id via get_redeemable_ids.py
2) Use this script to get the trade tx hash
3) Paste the tx hash into Alchemy's debug_traceTransaction UI
4) Save the JSON and decode with parse_trace_ctf_call.py
"""

from __future__ import annotations

import argparse
from datetime import datetime

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet


def _format_time(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List trade tx hashes for a token/condition id."
    )
    parser.add_argument(
        "position_id",
        help="Token id or condition id (numeric or 0x...)",
    )
    parser.add_argument(
        "--user",
        default=PROXY_WALLET,
        help="Wallet to query (defaults to proxy wallet).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Activity page size (default: 100).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Max pages to scan (default: 50).",
    )
    parser.add_argument(
        "--all-types",
        action="store_true",
        help="Query all activity types (no type filter).",
    )
    args = parser.parse_args()

    # Use activity history to locate trade txs for the target token/condition.
    token_or_condition = str(args.position_id)
    matches = []
    base_url = f"https://data-api.polymarket.com/activity?user={args.user}"
    if not args.all_types:
        base_url += "&type=TRADE"

    for page in range(args.max_pages):
        offset = page * args.page_size
        url = f"{base_url}&limit={args.page_size}&offset={offset}"
        activities = fetch_data(url)
        if not isinstance(activities, list) or not activities:
            break

        for activity in activities:
            asset = str(activity.get("asset") or "")
            condition_id = str(activity.get("conditionId") or "")
            if token_or_condition in {asset, condition_id}:
                matches.append(activity)

    if not matches:
        print(f"No trade activity found for: {token_or_condition}")
        return

    matches.sort(key=lambda a: int(a.get("timestamp") or 0), reverse=True)
    print(f"Found {len(matches)} trade(s) for {token_or_condition}")
    for activity in matches:
        tx_hash = activity.get("transactionHash") or ""
        ts = int(activity.get("timestamp") or 0)
        print(f"{_format_time(ts)}  {tx_hash}")

    latest_tx = matches[0].get("transactionHash") or ""
    if latest_tx:
        print(f"\nLatest tx hash to paste: {latest_tx}")


if __name__ == "__main__":
    main()
