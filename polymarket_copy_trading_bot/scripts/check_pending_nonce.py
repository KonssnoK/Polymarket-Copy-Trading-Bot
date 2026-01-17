"""Print confirmed vs pending nonce for the proxy wallet."""

from __future__ import annotations

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV

PROXY_WALLET = ENV.proxy_wallet
RPC_URL = ENV.rpc_url or "https://polygon-rpc.com"


def main() -> None:
    if not PROXY_WALLET:
        print("PROXY_WALLET is not set.")
        return

    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not web3.is_connected():
        print(f"Failed to connect to RPC: {RPC_URL}")
        return

    latest_nonce = web3.eth.get_transaction_count(PROXY_WALLET, "latest")
    pending_nonce = web3.eth.get_transaction_count(PROXY_WALLET, "pending")

    print(f"Wallet: {PROXY_WALLET}")
    print(f"Latest nonce (confirmed): {latest_nonce}")
    print(f"Pending nonce (next):     {pending_nonce}")

    if pending_nonce > latest_nonce:
        print("Pending transactions detected.")
        print(f"Oldest pending nonce:     {latest_nonce}")
        print(f"Next available nonce:     {pending_nonce}")
    else:
        print("No pending transactions detected.")


if __name__ == "__main__":
    main()
