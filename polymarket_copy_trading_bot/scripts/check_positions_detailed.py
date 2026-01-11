"""Detailed position listing."""

from __future__ import annotations

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet


def main() -> None:
    print("\nCURRENT POSITIONS:\n")

    positions = fetch_data(
        f"https://data-api.polymarket.com/positions?user={PROXY_WALLET}"
    ) or []

    if not positions:
        print("No open positions")
        return

    print(f"Found positions: {len(positions)}\n")

    sorted_positions = sorted(
        positions, key=lambda p: float(p.get("currentValue") or 0), reverse=True
    )

    total_value = 0.0

    for pos in sorted_positions:
        total_value += float(pos.get("currentValue") or 0)
        print("-" * 70)
        asset = pos.get("asset") or ""
        
        print(f"Market: {pos.get('title') or 'Unknown'} - Asset ID: {asset[:10]}...")
        print(f"Outcome: {pos.get('outcome') or 'Unknown'}")
        
        print(f"Size: {float(pos.get('size') or 0):.2f} shares @  Avg Price: ${float(pos.get('avgPrice') or 0):.4f} -> Current Price: ${float(pos.get('curPrice') or 0):.4f}")
        print(f"Initial Value: ${float(pos.get('initialValue') or 0):.2f} -> Current Value: ${float(pos.get('currentValue') or 0):.2f}")
        print(
            f"PnL: ${float(pos.get('cashPnl') or 0):.2f} ({float(pos.get('percentPnl') or 0):.2f}%)"
        )
        if pos.get("slug"):
            print(f"URL: https://polymarket.com/event/{pos.get('slug')}")

    print("\n" + "-" * 70)
    print(f"TOTAL CURRENT VALUE: ${total_value:.2f}")
    print("-" * 70 + "\n")

    large_positions = [p for p in sorted_positions if float(p.get("currentValue") or 0) > 5]

    if large_positions:
        print(f"\nLARGE POSITIONS (> $5): {len(large_positions)}\n")
        for pos in large_positions:
            title = pos.get("title") or "Unknown"
            outcome = pos.get("outcome") or "Unknown"
            current_value = float(pos.get("currentValue") or 0)
            size = float(pos.get("size") or 0)
            cur_price = float(pos.get("curPrice") or 0)
            print(
                f"- {title} [{outcome}]: ${current_value:.2f} ({size:.2f} shares @ ${cur_price:.4f})"
            )

        print("\nTo sell 80% of these positions, use:")
        print("  python -m polymarket_copy_trading_bot.scripts.manual_sell\n")

        print("Data for selling:\n")
        for pos in large_positions:
            sell_size = int(float(pos.get("size") or 0) * 0.8)
            print(f"  Asset ID: {pos.get('asset')}")
            print(f"  Size to sell: {sell_size} (80% of {float(pos.get('size') or 0):.2f})")
            print(f"  Market: {pos.get('title')} [{pos.get('outcome')}]\n")
    else:
        print("\nNo large positions (> $5)")


if __name__ == "__main__":
    main()