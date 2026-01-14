"""Lean position listing with IDs."""

from __future__ import annotations

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet


def _load_positions() -> list[dict]:
    positions = fetch_data(
        f"https://data-api.polymarket.com/positions?user={PROXY_WALLET}"
    )
    return positions if isinstance(positions, list) else []


def _format_title(position: dict, limit: int = 72) -> str:
    title = position.get("title") or position.get("slug") or "Unknown"
    if len(title) <= limit:
        return title
    return f"{title[: limit - 3]}..."


def main() -> None:
    positions = _load_positions()
    if not positions:
        print("No open positions")
        return

    sorted_positions = sorted(
        positions, key=lambda p: float(p.get("currentValue") or 0), reverse=True
    )

    print(f"Found positions: {len(sorted_positions)}\n")
    print("ID  | Value    | Size     | Token ID                                 | Outcome | Title")
    print("-" * 110)

    for idx, pos in enumerate(sorted_positions, start=1):
        token_id = pos.get("asset") or ""
        value = float(pos.get("currentValue") or 0)
        size = float(pos.get("size") or 0)
        outcome = pos.get("outcome") or "?"
        title = _format_title(pos)
        print(
            f"{idx:>3} | ${value:>7.2f} | {size:>7.2f} | {token_id:<40} | {outcome:<7} | {title}"
        )


if __name__ == "__main__":
    main()
