"""Check wallet statistics on Polymarket."""

from __future__ import annotations

from datetime import datetime

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data
from polymarket_copy_trading_bot.utils.get_my_balance import get_my_balance

PROXY_WALLET = ENV.proxy_wallet


def main() -> None:
    print("Checking your wallet statistics on Polymarket\n")
    print(f"Wallet: {PROXY_WALLET}\n")

    try:
        print("USDC BALANCE")
        balance = get_my_balance(PROXY_WALLET)
        print(f"  Available: ${balance:.2f}\n")

        print("OPEN POSITIONS")
        positions = fetch_data(
            f"https://data-api.polymarket.com/positions?user={PROXY_WALLET}"
        ) or []

        if positions:
            print(f"  Total positions: {len(positions)}\n")

            total_value = sum(float(p.get("currentValue") or 0) for p in positions)
            total_initial = sum(float(p.get("initialValue") or 0) for p in positions)
            total_unrealized = sum(float(p.get("cashPnl") or 0) for p in positions)
            total_realized = sum(float(p.get("realizedPnl") or 0) for p in positions)

            unrealized_pct = 0.0
            if total_initial:
                unrealized_pct = (total_unrealized / total_initial) * 100

            print(f"  Current value: ${total_value:.2f}")
            print(f"  Initial value: ${total_initial:.2f}")
            print(
                f"  Unrealized P&L: ${total_unrealized:.2f} ({unrealized_pct:.2f}%)"
            )
            print(f"  Realized P&L: ${total_realized:.2f}\n")

            print("  Top-5 positions by profit:\n")
            top_positions = sorted(
                positions,
                key=lambda p: float(p.get("percentPnl") or 0),
                reverse=True,
            )[:5]

            for idx, pos in enumerate(top_positions, start=1):
                pnl = float(pos.get("percentPnl") or 0)
                cash_pnl = float(pos.get("cashPnl") or 0)
                size = float(pos.get("size") or 0)
                avg_price = float(pos.get("avgPrice") or 0)
                cur_price = float(pos.get("curPrice") or 0)
                print(f"  {idx}. {pos.get('title') or 'Unknown'}")
                print(f"     {pos.get('outcome') or 'N/A'}")
                print(f"     Size: {size:.2f} tokens @ ${avg_price:.3f}")
                print(f"     P&L: ${cash_pnl:.2f} ({pnl:.2f}%)")
                print(f"     Current price: ${cur_price:.3f}")
                if pos.get("slug"):
                    print(f"     https://polymarket.com/event/{pos.get('slug')}")
                print("")
        else:
            print("  No open positions found\n")

        print("TRADE HISTORY (last 20)\n")
        activities = fetch_data(
            f"https://data-api.polymarket.com/activity?user={PROXY_WALLET}&type=TRADE"
        ) or []

        if activities:
            print(f"  Total trades in API: {len(activities)}\n")

            buys = [a for a in activities if a.get("side") == "BUY"]
            sells = [a for a in activities if a.get("side") == "SELL"]
            total_buy = sum(float(t.get("usdcSize") or 0) for t in buys)
            total_sell = sum(float(t.get("usdcSize") or 0) for t in sells)

            print("  Trade statistics:")
            print(f"    Buys: {len(buys)} (volume: ${total_buy:.2f})")
            print(f"    Sells: {len(sells)} (volume: ${total_sell:.2f})")
            print(f"    Total volume: ${(total_buy + total_sell):.2f}\n")

            print("  Last 20 trades:\n")
            for idx, trade in enumerate(activities[:20], start=1):
                date = datetime.fromtimestamp(int(trade.get("timestamp") or 0))
                tx_hash = trade.get("transactionHash") or ""
                print(f"  {idx}. {trade.get('side')} - {date}")
                print(f"     {trade.get('title') or 'Unknown Market'}")
                print(f"     {trade.get('outcome') or 'N/A'}")
                print(
                    f"     Volume: ${float(trade.get('usdcSize') or 0):.2f} @ ${float(trade.get('price') or 0):.3f}"
                )
                if tx_hash:
                    print(f"     TX: {tx_hash[:10]}...{tx_hash[-8:]}")
                    print(f"     https://polygonscan.com/tx/{tx_hash}")
                print("")
        else:
            print("  Trade history not found\n")

        print("WHY NO P&L CHARTS ON POLYMARKET?\n")
        print("  Profit/Loss charts only show realized profit (closed positions).\n")

        if positions:
            total_realized = sum(float(p.get("realizedPnl") or 0) for p in positions)
            total_unrealized = sum(float(p.get("cashPnl") or 0) for p in positions)
            print("  Realized P&L (closed positions):")
            print(f"    ${total_realized:.2f} is displayed on the chart\n")
            print("  Unrealized P&L (open positions):")
            print(f"    ${total_unrealized:.2f} is NOT displayed on the chart\n")
            if total_realized == 0:
                print("  Solution: close positions with profit and wait for API update.\n")

        print("Check completed!\n")
        print(f"Your profile: https://polymarket.com/profile/{PROXY_WALLET}\n")
    except Exception as exc:  # noqa: BLE001
        print(f"Error fetching data: {exc}")


if __name__ == "__main__":
    main()