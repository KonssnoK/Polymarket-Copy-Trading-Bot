"""Find Gnosis Safe proxy wallet from activity data."""

from __future__ import annotations

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PRIVATE_KEY = ENV.private_key
RPC_URL = ENV.rpc_url


def main() -> None:
    print("Find Gnosis Safe Proxy Wallet\n")

    wallet = Web3().eth.account.from_key(PRIVATE_KEY)
    eoa_address = wallet.address
    print(f"EOA address: {eoa_address}\n")

    print("Checking positions on EOA...")
    try:
        positions = fetch_data(
            f"https://data-api.polymarket.com/positions?user={eoa_address}"
        ) or []
        print(f"  Positions: {len(positions)}")
    except Exception:
        print("  Failed to fetch positions")

    print("\nChecking activity for proxyWallet field...")
    try:
        activities = fetch_data(
            f"https://data-api.polymarket.com/activity?user={eoa_address}&type=TRADE"
        ) or []
        if not activities:
            print("  No activity found")
            return

        proxy_wallet = activities[0].get("proxyWallet")
        print(f"  proxyWallet from trade: {proxy_wallet}")
        if proxy_wallet and proxy_wallet.lower() != eoa_address.lower():
            print("  Found proxy wallet in activity")
            proxy_positions = fetch_data(
                f"https://data-api.polymarket.com/positions?user={proxy_wallet}"
            ) or []
            print(f"  Proxy positions: {len(proxy_positions)}")
            if proxy_positions:
                print("\nUpdate .env:")
                print(f"  PROXY_WALLET={proxy_wallet}\n")
        else:
            print("  Proxy wallet matches EOA or not found")
    except Exception as exc:  # noqa: BLE001
        print(f"  Failed to inspect activity: {exc}")

    print("\nIf still unsure, check on Polymarket profile pages.")


if __name__ == "__main__":
    main()