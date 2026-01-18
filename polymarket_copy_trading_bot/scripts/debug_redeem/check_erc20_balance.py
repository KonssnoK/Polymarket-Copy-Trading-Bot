"""Check ERC20 balance for a wallet and token.

Use this after redemption to confirm whether funds landed in USDC or WCOL.
"""

from __future__ import annotations

import argparse

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV

RPC_URL = ENV.rpc_url or "https://polygon-rpc.com"
DEFAULT_WALLET = ENV.proxy_wallet

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Check ERC20 token balance.")
    parser.add_argument("token", help="ERC20 token contract address")
    parser.add_argument(
        "--wallet",
        default=DEFAULT_WALLET,
        help="Wallet address (defaults to ENV.proxy_wallet)",
    )
    args = parser.parse_args()

    # Direct RPC read of token balance.
    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not web3.is_connected():
        raise SystemExit("RPC connection failed.")

    token_address = Web3.to_checksum_address(args.token)
    wallet_address = Web3.to_checksum_address(args.wallet)
    contract = web3.eth.contract(address=token_address, abi=ERC20_ABI)

    balance = contract.functions.balanceOf(wallet_address).call()
    try:
        decimals = contract.functions.decimals().call()
    except Exception:
        decimals = 18
    try:
        symbol = contract.functions.symbol().call()
    except Exception:
        symbol = "TOKEN"

    human_balance = balance / (10 ** decimals) if decimals >= 0 else balance
    print(f"Wallet: {wallet_address}")
    print(f"Token: {token_address}")
    print(f"Symbol: {symbol}")
    print(f"Decimals: {decimals}")
    print(f"Balance (raw): {balance}")
    print(f"Balance: {human_balance:.6f} {symbol}")


if __name__ == "__main__":
    main()
