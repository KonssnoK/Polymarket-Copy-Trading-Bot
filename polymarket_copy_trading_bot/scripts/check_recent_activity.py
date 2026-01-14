"""Check recent activity after redemption."""

from __future__ import annotations

from datetime import datetime, timezone

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

WALLET = ENV.proxy_wallet


def main() -> None:
    url = f"https://data-api.polymarket.com/activity?user={WALLET}&type=TRADE"
    activities = fetch_data(url) or []

    if not activities:
        print("No trade data available")
        return

    redemption_end = datetime(2025, 10, 31, 18, 14, 16, tzinfo=timezone.utc).timestamp()

    print("CLOSED POSITIONS (Redeemed October 31, 2025 at 18:00-18:14)")
    print("TOTAL RECEIVED FROM REDEMPTION: $66.37 USDC\n")

    print("PURCHASES AFTER REDEMPTION (after 18:14 UTC October 31)\n")
    trades_after = [
        t for t in activities if t.get("timestamp", 0) > redemption_end and t.get("side") == "BUY"
    ]

    if not trades_after:
        print("No purchases after redemption. Funds should be in balance.")
        return

    total_spent = 0.0
    for idx, trade in enumerate(trades_after, start=1):
        date = datetime.fromtimestamp(int(trade.get("timestamp") or 0))
        value = float(trade.get("usdcSize") or 0)
        total_spent += value
        print(f"{idx}. BOUGHT: {trade.get('title') or trade.get('market') or 'Unknown'}")
        print(f"   Spent: ${value:.2f}")
        print(
            f"   Size: {float(trade.get('size') or 0):.2f} tokens @ ${float(trade.get('price') or 0):.4f}"
        )
        print(f"   Date: {date}")
        tx_hash = trade.get("transactionHash") or ""
        if tx_hash:
            print(f"   TX: https://polygonscan.com/tx/{tx_hash[:20]}...\n")

    print("TOTAL PURCHASES AFTER REDEMPTION:")
    print(f"  Number of trades: {len(trades_after)}")
    print(f"  SPENT: ${total_spent:.2f} USDC\n")

    print("EXPLANATION OF WHERE THE MONEY WENT:\n")
    print("  Received from redemption: +$66.37")
    print(f"  Spent on new purchases: -${total_spent:.2f}")
    print(f"  Balance change: ${(66.37 - total_spent):.2f}\n")

    print("RECENT SALES:\n")
    recent_sells = [t for t in activities if t.get("side") == "SELL"][:10]
    total_sold = 0.0
    for idx, trade in enumerate(recent_sells, start=1):
        date = datetime.fromtimestamp(int(trade.get("timestamp") or 0))
        value = float(trade.get("usdcSize") or 0)
        total_sold += value
        print(f"{idx}. SOLD: {trade.get('title') or trade.get('market') or 'Unknown'}")
        print(f"   Received: ${value:.2f}")
        print(f"   Date: {date}\n")

    print(f"Sold in recent trades: ${total_sold:.2f}")


if __name__ == "__main__":
    main()