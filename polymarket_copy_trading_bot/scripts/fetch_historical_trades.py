"""Fetch historical trades for configured trader addresses."""

from __future__ import annotations

import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from polymarket_copy_trading_bot.config.env import ENV

USER_ADDRESSES = ENV.user_addresses

HISTORY_DAYS = int(os.getenv("HISTORY_DAYS", "30"))
MAX_TRADES_PER_TRADER = int(os.getenv("HISTORY_MAX_TRADES", "20000"))
BATCH_SIZE = min(int(os.getenv("HISTORY_BATCH_SIZE", "100")), 1000)
MAX_PARALLEL = min(int(os.getenv("HISTORY_MAX_PARALLEL", "4")), 10)


def _fetch_batch(address: str, offset: int, limit: int) -> list[dict[str, Any]]:
    response = requests.get(
        f"https://data-api.polymarket.com/activity?user={address}&type=TRADE&limit={limit}&offset={offset}",
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def _fetch_trades_for_trader(address: str) -> list[dict[str, Any]]:
    print(f"\nFetching trades for {address} (last {HISTORY_DAYS} days)")
    since_ts = int(time.time()) - HISTORY_DAYS * 24 * 60 * 60

    offset = 0
    all_trades: list[dict[str, Any]] = []
    has_more = True

    while has_more and len(all_trades) < MAX_TRADES_PER_TRADER:
        batch_limit = min(BATCH_SIZE, MAX_TRADES_PER_TRADER - len(all_trades))
        batch = _fetch_batch(address, offset, batch_limit)
        if not batch:
            has_more = False
            break

        filtered = [trade for trade in batch if int(trade.get("timestamp") or 0) >= since_ts]
        all_trades.extend(filtered)

        if len(batch) < batch_limit or len(filtered) < len(batch):
            has_more = False

        offset += batch_limit
        if len(all_trades) % max(BATCH_SIZE * MAX_PARALLEL, 1) == 0:
            time.sleep(0.15)

    all_trades.sort(key=lambda t: int(t.get("timestamp") or 0))
    print(f"Fetched {len(all_trades)} trades")
    return all_trades


def _save_trades(address: str, trades: list[dict[str, Any]]) -> None:
    cache_dir = Path.cwd() / "trader_data_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    cache_file = cache_dir / f"{address}_{HISTORY_DAYS}d_{today}.json"

    payload = {
        "name": f"trader_{address[:6]}_{HISTORY_DAYS}d_{today}",
        "traderAddress": address,
        "fetchedAt": datetime.utcnow().isoformat(),
        "period": f"{HISTORY_DAYS}_days",
        "historyDays": HISTORY_DAYS,
        "totalTrades": len(trades),
        "trades": trades,
    }

    cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved to {cache_file}")


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def main() -> None:
    if not USER_ADDRESSES:
        print("USER_ADDRESSES is empty. Check .env")
        return

    print("Fetching historical trades for configured traders")
    print(f"Traders: {len(USER_ADDRESSES)}")
    print(
        f"History: {HISTORY_DAYS} days, max {MAX_TRADES_PER_TRADER} trades per trader"
    )

    for group in _chunk(USER_ADDRESSES, MAX_PARALLEL):
        with ThreadPoolExecutor(max_workers=len(group)) as executor:
            futures = [executor.submit(_fetch_trades_for_trader, addr) for addr in group]
            for address, future in zip(group, futures):
                try:
                    trades = future.result()
                    _save_trades(address, trades)
                except Exception as exc:  # noqa: BLE001
                    print(f"Failed to fetch trades for {address}: {exc}")

    print("\nDone fetching historical trades")


if __name__ == "__main__":
    main()