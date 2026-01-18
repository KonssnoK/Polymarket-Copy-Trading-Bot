"""Unwrap WCOL to the underlying collateral (USDC)."""

from __future__ import annotations

import argparse
from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV

RPC_URL = ENV.rpc_url or "https://polygon-rpc.com"
PROXY_WALLET = ENV.proxy_wallet
PRIVATE_KEY = ENV.private_key

WCOL_CONTRACT = "0x3a3bd7bb9528e159577f7c2e685cc81a765002e2"

WCOL_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "_to", "type": "address"},
            {"internalType": "uint256", "name": "_amount", "type": "uint256"},
        ],
        "name": "unwrap",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

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
]


def _resolve_amount(web3: Web3, wallet: str, amount: float | None, raw: int | None) -> int:
    if raw is not None:
        return raw
    contract = web3.eth.contract(address=Web3.to_checksum_address(WCOL_CONTRACT), abi=ERC20_ABI)
    decimals = contract.functions.decimals().call()
    if amount is None:
        balance = contract.functions.balanceOf(Web3.to_checksum_address(wallet)).call()
        return int(balance)
    return int(amount * (10**decimals))


def main() -> None:
    parser = argparse.ArgumentParser(description="Unwrap WCOL to USDC.")
    parser.add_argument(
        "--amount",
        type=float,
        default=None,
        help="Amount in human units (defaults to full balance)",
    )
    parser.add_argument(
        "--amount-raw",
        type=int,
        default=None,
        help="Raw amount (overrides --amount)",
    )
    parser.add_argument(
        "--to",
        default=None,
        help="Recipient address for unwrapped USDC (defaults to proxy wallet)",
    )
    args = parser.parse_args()

    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not web3.is_connected():
        raise SystemExit("RPC connection failed.")

    to_address = Web3.to_checksum_address(args.to or PROXY_WALLET)
    amount_raw = _resolve_amount(web3, PROXY_WALLET, args.amount, args.amount_raw)
    if amount_raw <= 0:
        raise SystemExit("No WCOL balance available to unwrap.")

    wcol = web3.eth.contract(
        address=Web3.to_checksum_address(WCOL_CONTRACT),
        abi=WCOL_ABI,
    )
    func = wcol.get_function_by_name("unwrap")(to_address, amount_raw)

    tx = func.build_transaction(
        {
            "from": Web3.to_checksum_address(PROXY_WALLET),
            "nonce": web3.eth.get_transaction_count(PROXY_WALLET, "pending"),
            "gas": 200000,
            "gasPrice": web3.eth.gas_price,
        }
    )
    signed = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Transaction submitted: {tx_hash.hex()}")


if __name__ == "__main__":
    main()
