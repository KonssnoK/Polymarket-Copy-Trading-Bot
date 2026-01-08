"""Check proxy wallet vs main wallet activity."""

from __future__ import annotations

from datetime import datetime

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet
PRIVATE_KEY = ENV.private_key
RPC_URL = ENV.rpc_url


def _format_date(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%m/%d/%Y")


def main() -> None:
    print("CHECKING PROXY WALLET AND MAIN WALLET\n")

    wallet = Web3().eth.account.from_key(PRIVATE_KEY)
    eoa_address = wallet.address

    print("YOUR ADDRESSES:\n")
    print(f"  EOA (Main wallet):  {eoa_address}")
    print(f"  Proxy Wallet:       {PROXY_WALLET}\n")

    print("CHECKING ACTIVITY ON MAIN WALLET (EOA):\n")
    eoa_activities = fetch_data(
        f"https://data-api.polymarket.com/activity?user={eoa_address}&type=TRADE"
    ) or []

    print(f"  Address: {eoa_address}")
    print(f"  Trades: {len(eoa_activities)}")
    print(f"  Profile: https://polymarket.com/profile/{eoa_address}\n")

    if eoa_activities:
        buys = [a for a in eoa_activities if a.get("side") == "BUY"]
        sells = [a for a in eoa_activities if a.get("side") == "SELL"]
        total_buy = sum(float(t.get("usdcSize") or 0) for t in buys)
        total_sell = sum(float(t.get("usdcSize") or 0) for t in sells)
        print("  EOA Statistics:")
        print(f"    Buys: {len(buys)} (${total_buy:.2f})")
        print(f"    Sells: {len(sells)} (${total_sell:.2f})")
        print(f"    Volume: ${(total_buy + total_sell):.2f}\n")

        print("  Last 3 trades:")
        for idx, trade in enumerate(eoa_activities[:3], start=1):
            date_str = _format_date(int(trade.get("timestamp") or 0))
            print(f"    {idx}. {trade.get('side')} - {trade.get('title') or 'Unknown'}")
            print(f"       ${float(trade.get('usdcSize') or 0):.2f} @ {date_str}")
        print("")
    else:
        print("  No trades found on main wallet\n")

    print("CHECKING ACTIVITY ON PROXY WALLET (CONTRACT):\n")
    proxy_activities = fetch_data(
        f"https://data-api.polymarket.com/activity?user={PROXY_WALLET}&type=TRADE"
    ) or []

    print(f"  Address: {PROXY_WALLET}")
    print(f"  Trades: {len(proxy_activities)}")
    print(f"  Profile: https://polymarket.com/profile/{PROXY_WALLET}\n")

    if proxy_activities:
        buys = [a for a in proxy_activities if a.get("side") == "BUY"]
        sells = [a for a in proxy_activities if a.get("side") == "SELL"]
        total_buy = sum(float(t.get("usdcSize") or 0) for t in buys)
        total_sell = sum(float(t.get("usdcSize") or 0) for t in sells)
        print("  Proxy Wallet Statistics:")
        print(f"    Buys: {len(buys)} (${total_buy:.2f})")
        print(f"    Sells: {len(sells)} (${total_sell:.2f})")
        print(f"    Volume: ${(total_buy + total_sell):.2f}\n")

        print("  Last 3 trades:")
        for idx, trade in enumerate(proxy_activities[:3], start=1):
            date_str = _format_date(int(trade.get("timestamp") or 0))
            print(f"    {idx}. {trade.get('side')} - {trade.get('title') or 'Unknown'}")
            print(f"       ${float(trade.get('usdcSize') or 0):.2f} @ {date_str}")
        print("")
    else:
        print("  No trades found on proxy wallet\n")

    print("CONNECTION BETWEEN ADDRESSES:\n")
    if eoa_activities:
        print(f"  EOA trades contain proxyWallet: {eoa_activities[0].get('proxyWallet')}")
    if proxy_activities:
        print(
            f"  Proxy trades contain proxyWallet: {proxy_activities[0].get('proxyWallet')}"
        )

    print("\nHOW IT WORKS:\n")
    print("  1) EOA (Externally Owned Account) - your main wallet")
    print("  2) Proxy Wallet - smart contract wallet executing trades")

    print("WHY NO STATISTICS ON PROFILE?\n")
    eoa_has_trades = bool(eoa_activities)
    proxy_has_trades = bool(proxy_activities)

    if not eoa_has_trades and proxy_has_trades:
        print("  PROBLEM FOUND: trades go through proxy wallet")
        print("  Use proxy wallet address to view stats:")
        print(f"  https://polymarket.com/profile/{PROXY_WALLET}\n")
    elif eoa_has_trades and not proxy_has_trades:
        print("  Trades go through main wallet; stats should be on EOA profile.\n")
    elif eoa_has_trades and proxy_has_trades:
        print("  Trades exist on both addresses; you may have used multiple wallets.\n")
    else:
        print("  No trades found on any address.\n")

    print("BLOCKCHAIN CHECK:\n")
    print(f"  EOA: https://polygonscan.com/address/{eoa_address}")
    print(f"  Proxy: https://polygonscan.com/address/{PROXY_WALLET}\n")

    try:
        provider = Web3(Web3.HTTPProvider(RPC_URL))
        eoa_code = provider.eth.get_code(eoa_address)
        proxy_code = provider.eth.get_code(PROXY_WALLET)
        print("  Address types:")
        print("    EOA:", "Regular wallet" if eoa_code in (b"", b"0x") else "Contract")
        print("    Proxy:", "Contract" if proxy_code not in (b"", b"0x") else "Regular wallet")
    except Exception:
        print("  Failed to check address types via RPC")

    print("\nSUMMARY:\n")
    print("  Bot uses PROXY_WALLET for trading.")
    print(f"  Profile: https://polymarket.com/profile/{PROXY_WALLET}\n")


if __name__ == "__main__":
    main()