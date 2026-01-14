"""Detailed P&L discrepancy check."""

from __future__ import annotations

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet


def main() -> None:
    print("Detailed P&L discrepancy check\n")
    print(f"Wallet: {PROXY_WALLET}\n")

    try:
        positions = fetch_data(
            f"https://data-api.polymarket.com/positions?user={PROXY_WALLET}"
        ) or []

        print(f"Fetched positions: {len(positions)}\n")

        open_positions = [p for p in positions if float(p.get("size") or 0) > 0]
        closed_positions = [p for p in positions if float(p.get("size") or 0) == 0]

        print(f"Open: {len(open_positions)}")
        print(f"Closed: {len(closed_positions)}\n")

        print("OPEN POSITIONS:\n")
        total_open_value = 0.0
        total_open_initial = 0.0
        total_unrealized = 0.0
        total_open_realized = 0.0

        for idx, pos in enumerate(open_positions, start=1):
            total_open_value += float(pos.get("currentValue") or 0)
            total_open_initial += float(pos.get("initialValue") or 0)
            total_unrealized += float(pos.get("cashPnl") or 0)
            total_open_realized += float(pos.get("realizedPnl") or 0)

            print(f"{idx}. {pos.get('title') or 'Unknown'} - {pos.get('outcome') or 'N/A'}")
            print(f"   Size: {float(pos.get('size') or 0):.2f} @ ${float(pos.get('avgPrice') or 0):.3f}")
            print(f"   Current Value: ${float(pos.get('currentValue') or 0):.2f}")
            print(f"   Initial Value: ${float(pos.get('initialValue') or 0):.2f}")
            print(
                f"   Unrealized P&L: ${float(pos.get('cashPnl') or 0):.2f} ({float(pos.get('percentPnl') or 0):.2f}%)"
            )
            print(f"   Realized P&L: ${float(pos.get('realizedPnl') or 0):.2f}\n")

        print("TOTAL for open:")
        print(f"  Current value: ${total_open_value:.2f}")
        print(f"  Initial value: ${total_open_initial:.2f}")
        print(f"  Unrealized P&L: ${total_unrealized:.2f}")
        print(f"  Realized P&L: ${total_open_realized:.2f}\n")

        print("CLOSED POSITIONS:\n")
        total_closed_realized = 0.0
        total_closed_initial = 0.0

        if closed_positions:
            for idx, pos in enumerate(closed_positions, start=1):
                total_closed_realized += float(pos.get("realizedPnl") or 0)
                total_closed_initial += float(pos.get("initialValue") or 0)

                print(f"{idx}. {pos.get('title') or 'Unknown'} - {pos.get('outcome') or 'N/A'}")
                print(f"   Initial Value: ${float(pos.get('initialValue') or 0):.2f}")
                print(f"   Realized P&L: ${float(pos.get('realizedPnl') or 0):.2f}")
                print(f"   % P&L: {float(pos.get('percentRealizedPnl') or 0):.2f}%\n")

            print("TOTAL for closed:")
            print(f"  Initial investments: ${total_closed_initial:.2f}")
            print(f"  Realized P&L: ${total_closed_realized:.2f}\n")
        else:
            print("  No closed positions found in API\n")

        print("OVERALL STATISTICS:\n")
        total_realized = total_open_realized + total_closed_realized
        print(f"  Open positions - Realized P&L: ${total_open_realized:.2f}")
        print(f"  Closed positions - Realized P&L: ${total_closed_realized:.2f}")
        print(f"  Unrealized P&L: ${total_unrealized:.2f}")
        print(f"  TOTAL REALIZED PROFIT: ${total_realized:.2f}\n")

        print("CHECK THROUGH TRADE HISTORY:\n")
        activities = fetch_data(
            f"https://data-api.polymarket.com/activity?user={PROXY_WALLET}&type=TRADE"
        ) or []

        market_trades: dict[str, dict[str, list]] = {}
        for trade in activities:
            key = f"{trade.get('conditionId')}:{trade.get('asset')}"
            if key not in market_trades:
                market_trades[key] = {"buys": [], "sells": []}
            if trade.get("side") == "BUY":
                market_trades[key]["buys"].append(trade)
            else:
                market_trades[key]["sells"].append(trade)

        print(f"  Found markets with activity: {len(market_trades)}\n")

        calculated_realized = 0.0
        markets_with_profit = 0

        for trades in market_trades.values():
            total_bought = sum(float(t.get("usdcSize") or 0) for t in trades["buys"])
            total_sold = sum(float(t.get("usdcSize") or 0) for t in trades["sells"])
            pnl = total_sold - total_bought
            if abs(pnl) > 0.01:
                market = trades["buys"][0] if trades["buys"] else trades["sells"][0]
                print(f"  {market.get('title') or 'Unknown'}")
                print(f"    Bought: ${total_bought:.2f}")
                print(f"    Sold: ${total_sold:.2f}")
                print(f"    P&L: ${pnl:.2f}\n")
                if total_sold > 0:
                    calculated_realized += pnl
                    markets_with_profit += 1

        print(f"  Calculated realized profit: ${calculated_realized:.2f}")
        print(f"  Markets with closed profit: {markets_with_profit}\n")

        print("CONCLUSIONS:\n")
        print(f"  1. API returns realized profit: ${total_realized:.2f}")
        print(f"  2. Calculated from trade history: ${calculated_realized:.2f}")
        print("  3. Polymarket UI shows: ~$12.02\n")

        if abs(total_realized - calculated_realized) > 1:
            print("  DISCREPANCY DETECTED!\n")
            print("  Possible reasons:")
            print("   - API only counts partially closed positions")
            print("   - UI includes unrealized partial sales")
            print("   - Data synchronization delay between UI and API")
            print("   - Different P&L calculation methodology\n")

        print("  Why chart shows $0.00:")
        print("   - Amount too small for visualization")
        print("   - Chart requires several data points")
        print("   - UI update delay (1-24 hours)\n")

        print("  Recommendations:")
        print("   1. Wait 24 hours for full update")
        print("   2. Close more positions to increase realized profit")
        print("   3. Try clearing browser cache")
        print("   4. Check in incognito mode\n")
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()