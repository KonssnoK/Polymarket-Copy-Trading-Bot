"""List redeemable positions with lean IDs."""

from __future__ import annotations

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet
ZERO_THRESHOLD = 0.0001


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

    redeemable = [
        pos
        for pos in sorted_positions
        if pos.get("redeemable") is True
        and float(pos.get("size") or 0) > ZERO_THRESHOLD
    ]

    if not redeemable:
        print("No redeemable positions found")
        return

    print(f"Redeemable positions: {len(redeemable)}\n")
    print("ID  | Value    | Size     | Token ID                                 | Outcome | Title")
    print("-" * 110)

    redeemable_ids = {pos.get("asset") for pos in redeemable}
    for idx, pos in enumerate(sorted_positions, start=1):
        token_id = pos.get("asset") or ""
        if token_id not in redeemable_ids:
            continue
        value = float(pos.get("currentValue") or 0)
        size = float(pos.get("size") or 0)
        outcome = pos.get("outcome") or "?"
        title = _format_title(pos)
        print(
            f"{idx:>3} | ${value:>7.2f} | {size:>7.2f} | {token_id:<40} | {outcome:<7} | {title}"
        )


if __name__ == "__main__":
    main()
