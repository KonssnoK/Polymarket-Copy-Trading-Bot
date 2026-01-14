"""Check both wallet addresses for activity differences."""

from __future__ import annotations

from datetime import datetime

from polymarket_copy_trading_bot.utils.fetch_data import fetch_data
from polymarket_copy_trading_bot.utils.get_my_balance import get_my_balance


def _format_date(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%m/%d/%Y, %I:%M:%S %p")


def main() -> None:
    print("CHECKING BOTH ADDRESSES\n")

    address_1 = "0x4fbBe5599c06e846D2742014c9eB04A8a3d1DE8C"
    address_2 = "0xd62531bc536bff72394fc5ef715525575787e809"

    try:
        print("ADDRESS 1 (from .env - PROXY_WALLET):\n")
        print(f"  {address_1}")
        print(f"  Profile: https://polymarket.com/profile/{address_1}\n")

        addr1_activities = fetch_data(
            f"https://data-api.polymarket.com/activity?user={address_1}&type=TRADE"
        )
        addr1_positions = fetch_data(
            f"https://data-api.polymarket.com/positions?user={address_1}"
        )

        addr1_activities = addr1_activities or []
        addr1_positions = addr1_positions or []

        print(f"  Trades in API: {len(addr1_activities)}")
        print(f"  Positions in API: {len(addr1_positions)}")

        if addr1_activities:
            buys = [a for a in addr1_activities if a.get("side") == "BUY"]
            sells = [a for a in addr1_activities if a.get("side") == "SELL"]
            total_volume = sum(float(t.get("usdcSize") or 0) for t in buys + sells)
            print(f"  Buys: {len(buys)}")
            print(f"  Sells: {len(sells)}")
            print(f"  Volume: ${total_volume:.2f}")
            proxy_wallet = addr1_activities[0].get("proxyWallet")
            if proxy_wallet:
                print(f"  proxyWallet in trades: {proxy_wallet}")

        try:
            balance1 = get_my_balance(address_1)
            print(f"  USDC Balance: ${balance1:.2f}")
        except Exception:
            print("  USDC Balance: failed to get")

        print("\n" + "-" * 70 + "\n")

        print("ADDRESS 2 (from profile @shbot):\n")
        print(f"  {address_2}")
        print(f"  Profile: https://polymarket.com/profile/{address_2}\n")

        addr2_activities = fetch_data(
            f"https://data-api.polymarket.com/activity?user={address_2}&type=TRADE"
        )
        addr2_positions = fetch_data(
            f"https://data-api.polymarket.com/positions?user={address_2}"
        )

        addr2_activities = addr2_activities or []
        addr2_positions = addr2_positions or []

        print(f"  Trades in API: {len(addr2_activities)}")
        print(f"  Positions in API: {len(addr2_positions)}")

        if addr2_activities:
            buys = [a for a in addr2_activities if a.get("side") == "BUY"]
            sells = [a for a in addr2_activities if a.get("side") == "SELL"]
            total_volume = sum(float(t.get("usdcSize") or 0) for t in buys + sells)
            print(f"  Buys: {len(buys)}")
            print(f"  Sells: {len(sells)}")
            print(f"  Volume: ${total_volume:.2f}")
            proxy_wallet = addr2_activities[0].get("proxyWallet")
            if proxy_wallet:
                print(f"  proxyWallet in trades: {proxy_wallet}")

            print("\n  Last 5 trades:")
            for idx, trade in enumerate(addr2_activities[:5], start=1):
                date_str = _format_date(int(trade.get("timestamp") or 0))
                title = trade.get("title") or "Unknown"
                tx_hash = trade.get("transactionHash") or ""
                print(f"    {idx}. {trade.get('side')} - {title}")
                print(f"       ${float(trade.get('usdcSize') or 0):.2f} @ {date_str}")
                if tx_hash:
                    print(f"       TX: {tx_hash[:10]}...{tx_hash[-6:]}")

        try:
            balance2 = get_my_balance(address_2)
            print(f"\n  USDC Balance: ${balance2:.2f}")
        except Exception:
            print("\n  USDC Balance: failed to get")

        print("\n" + "-" * 70 + "\n")

        print("ADDRESS COMPARISON:\n")
        addr1_has = bool(addr1_activities or addr1_positions)
        addr2_has = bool(addr2_activities or addr2_positions)
        print(f"  Address 1 ({address_1[:8]}...): {'Has data' if addr1_has else 'No data'}")
        print(f"    Trades: {len(addr1_activities)}")
        print(f"    Positions: {len(addr1_positions)}\n")
        print(f"  Address 2 ({address_2[:8]}...): {'Has data' if addr2_has else 'No data'}")
        print(f"    Trades: {len(addr2_activities)}")
        print(f"    Positions: {len(addr2_positions)}\n")

        print("CONNECTION BETWEEN ADDRESSES:\n")
        if addr1_activities and addr2_activities:
            proxy1 = (addr1_activities[0].get("proxyWallet") or "").lower()
            proxy2 = (addr2_activities[0].get("proxyWallet") or "").lower()
            print(f"  Address 1 uses proxyWallet: {proxy1}")
            print(f"  Address 2 uses proxyWallet: {proxy2}\n")
            if proxy1 == proxy2 and proxy1:
                print("  BOTH ADDRESSES LINKED TO ONE PROXY WALLET!\n")
            elif proxy1 == address_2.lower():
                print("  CONNECTION FOUND!\n")
            elif proxy2 == address_1.lower():
                print("  CONNECTION FOUND!\n")
            else:
                print("  Addresses use different proxy wallets\n")

        print("PROFILE @shbot:\n")
        print("  Profile URL options:")
        print("  https://polymarket.com/@shbot")
        print(f"  https://polymarket.com/profile/{address_1}")
        print(f"  https://polymarket.com/profile/{address_2}\n")

        print("SUMMARY AND SOLUTION:\n")
        if addr2_has and not addr1_has:
            print("  YOUR BOT IS USING THE WRONG ADDRESS!\n")
            print(f"  All trading goes through address: {address_2}")
            print(f"  But .env specifies: {address_1}\n")
            print("  SOLUTION: Update .env file:\n")
            print(f"  PROXY_WALLET={address_2}\n")
        elif addr1_has and not addr2_has:
            print("  Bot is working correctly!")
            print("  Trading goes through address from .env\n")
        elif addr1_has and addr2_has:
            print("  Activity on BOTH addresses!\n")
            if addr1_activities and addr2_activities:
                last_trade1 = datetime.fromtimestamp(int(addr1_activities[0].get("timestamp") or 0))
                last_trade2 = datetime.fromtimestamp(int(addr2_activities[0].get("timestamp") or 0))
                print("  Last trade:")
                print(f"  Address 1: {last_trade1}")
                print(f"  Address 2: {last_trade2}\n")
                if abs((last_trade1 - last_trade2).total_seconds()) < 60:
                    print("  Trades synchronized (< 1 minute difference)")
        else:
            print("  No data on any address!\n")

    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()