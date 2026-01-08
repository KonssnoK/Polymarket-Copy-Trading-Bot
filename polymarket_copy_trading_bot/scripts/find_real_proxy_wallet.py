"""Find the real proxy wallet using API and on-chain clues."""

from __future__ import annotations

import os
import requests
from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PRIVATE_KEY = ENV.private_key
RPC_URL = ENV.rpc_url

POLYGONSCAN_API_KEY = os.getenv("POLYGONSCAN_API_KEY", "")


def main() -> None:
    print("Find real proxy wallet\n")

    wallet = Web3().eth.account.from_key(PRIVATE_KEY)
    eoa_address = wallet.address
    print(f"EOA address: {eoa_address}\n")

    print("Step 1: Query user profile API")
    try:
        profile = fetch_data(f"https://data-api.polymarket.com/users/{eoa_address}")
        print(profile)
    except Exception:
        print("  Failed to fetch user profile")

    print("\nStep 2: Inspect recent trades for proxyWallet")
    try:
        activities = fetch_data(
            f"https://data-api.polymarket.com/activity?user={eoa_address}&type=TRADE"
        ) or []
        if activities:
            proxy_wallet = activities[0].get("proxyWallet")
            print(f"  proxyWallet from trade: {proxy_wallet}")
            if proxy_wallet and proxy_wallet.lower() != eoa_address.lower():
                positions = fetch_data(
                    f"https://data-api.polymarket.com/positions?user={proxy_wallet}"
                ) or []
                if positions:
                    print("\nUpdate .env:")
                    print(f"  PROXY_WALLET={proxy_wallet}\n")
                    return
    except Exception:
        print("  Failed to fetch trade activity")

    print("\nStep 3: Check Polygonscan transactions (optional)")
    if not POLYGONSCAN_API_KEY:
        print("  POLYGONSCAN_API_KEY not set; skipping")
    else:
        url = (
            "https://api.polygonscan.com/api?module=account&action=txlist"
            f"&address={eoa_address}&startblock=0&endblock=99999999&page=1&offset=100"
            f"&sort=desc&apikey={POLYGONSCAN_API_KEY}"
        )
        try:
            response = requests.get(url, timeout=15)
            data = response.json()
            if data.get("status") == "1":
                txs = data.get("result", [])
                print(f"  Transactions fetched: {len(txs)}")
            else:
                print("  Polygonscan returned no data")
        except Exception:
            print("  Failed to query Polygonscan")

    print("\nStep 4: Check USDC balance and transfers (optional)")
    try:
        provider = Web3(Web3.HTTPProvider(RPC_URL))
        usdc_address = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"
        usdc_abi = [
            {"name": "balanceOf", "outputs": [{"type": "uint256"}], "inputs": [{"type": "address"}], "stateMutability": "view", "type": "function"}
        ]
        usdc_contract = provider.eth.contract(address=usdc_address, abi=usdc_abi)
        balance = usdc_contract.functions.balanceOf(eoa_address).call()
        print(f"  USDC balance: {balance / 1_000_000:.2f}")
    except Exception:
        print("  Failed to read USDC balance")

    print("\nManual steps:")
    print("  1) Log in to Polymarket and inspect your profile address")
    print("  2) Update PROXY_WALLET in .env")


if __name__ == "__main__":
    main()