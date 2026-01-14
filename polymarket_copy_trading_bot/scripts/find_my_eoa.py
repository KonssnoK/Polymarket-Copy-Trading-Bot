"""Analyze EOA vs proxy wallet configuration."""

from __future__ import annotations

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PRIVATE_KEY = ENV.private_key
PROXY_WALLET = ENV.proxy_wallet
RPC_URL = ENV.rpc_url


def main() -> None:
    print("Analyze EOA vs Proxy Wallet\n")

    wallet = Web3().eth.account.from_key(PRIVATE_KEY)
    eoa_address = wallet.address

    print("Step 1: Derived EOA address")
    print(f"  {eoa_address}\n")

    print("Step 2: PROXY_WALLET from .env")
    print(f"  {PROXY_WALLET}\n")

    print("Step 3: Compare addresses")
    if eoa_address.lower() == PROXY_WALLET.lower():
        print("  Warning: EOA equals PROXY_WALLET. Polymarket typically uses a proxy contract.")
    else:
        print("  OK: EOA and PROXY_WALLET are different.")
    print("")

    print("Step 4: Check PROXY_WALLET contract code")
    provider = Web3(Web3.HTTPProvider(RPC_URL))
    code = provider.eth.get_code(PROXY_WALLET)
    is_contract = code not in (b"", b"0x")
    print(f"  Type: {'Contract' if is_contract else 'EOA'}\n")

    print("Step 5: Check Polymarket data")
    try:
        proxy_positions = fetch_data(
            f"https://data-api.polymarket.com/positions?user={PROXY_WALLET}"
        ) or []
        print(f"  Proxy positions: {len(proxy_positions)}")

        if eoa_address.lower() != PROXY_WALLET.lower():
            eoa_positions = fetch_data(
                f"https://data-api.polymarket.com/positions?user={eoa_address}"
            ) or []
            print(f"  EOA positions: {len(eoa_positions)}")
    except Exception:
        print("  Failed to fetch positions")

    print("\nStep 6: Check proxyWallet from trade activity")
    try:
        activities = fetch_data(
            f"https://data-api.polymarket.com/activity?user={PROXY_WALLET}&type=TRADE"
        ) or []
        if activities:
            proxy_wallet_in_trade = activities[0].get("proxyWallet")
            print(f"  proxyWallet in trade: {proxy_wallet_in_trade}")
            if proxy_wallet_in_trade and proxy_wallet_in_trade.lower() == PROXY_WALLET.lower():
                print("  OK: proxy wallet matches .env")
            else:
                print("  Warning: proxy wallet differs from .env")
        else:
            print("  No trade activity found")
    except Exception:
        print("  Failed to fetch trade activity")

    print("\nRecommended checks:")
    print(f"  Polymarket profile: https://polymarket.com/profile/{PROXY_WALLET}")
    print(f"  Polygonscan (EOA): https://polygonscan.com/address/{eoa_address}")
    print(f"  Polygonscan (Proxy): https://polygonscan.com/address/{PROXY_WALLET}")


if __name__ == "__main__":
    main()