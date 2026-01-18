"""Attempt to extract redeem params from a transaction or activity history.

Use this only if the tx directly calls the CTF contract. Most trades go
through the exchange, so this often returns "not in tx input".
"""

from __future__ import annotations

import argparse

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

RPC_URL = ENV.rpc_url or "https://polygon-rpc.com"
PROXY_WALLET = ENV.proxy_wallet

CTF_CONTRACT_ADDRESS = Web3.to_checksum_address(
    "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
)

CTF_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "collateralToken", "type": "address"},
            {"internalType": "bytes32", "name": "parentCollectionId", "type": "bytes32"},
            {"internalType": "bytes32", "name": "conditionId", "type": "bytes32"},
            {"internalType": "uint256[]", "name": "partition", "type": "uint256[]"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "splitPosition",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "collateralToken", "type": "address"},
            {"internalType": "bytes32", "name": "parentCollectionId", "type": "bytes32"},
            {"internalType": "bytes32", "name": "conditionId", "type": "bytes32"},
            {"internalType": "uint256[]", "name": "partition", "type": "uint256[]"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "mergePositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "collateralToken", "type": "address"},
            {"internalType": "bytes32", "name": "parentCollectionId", "type": "bytes32"},
            {"internalType": "bytes32", "name": "conditionId", "type": "bytes32"},
            {"internalType": "uint256[]", "name": "indexSets", "type": "uint256[]"},
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


def _find_trade_tx(token_or_condition: str) -> str | None:
    activities = fetch_data(
        f"https://data-api.polymarket.com/activity?user={PROXY_WALLET}&type=TRADE"
    )
    if not isinstance(activities, list):
        return None

    for activity in activities:
        asset = str(activity.get("asset") or "")
        condition_id = str(activity.get("conditionId") or "")
        if token_or_condition in {asset, condition_id}:
            return str(activity.get("transactionHash") or "")
    return None


def _decode_ctf_tx(web3: Web3, tx_hash: str) -> None:
    tx = web3.eth.get_transaction(tx_hash)
    if not tx:
        print(f"Transaction not found: {tx_hash}")
        return

    to_address = tx.get("to")
    if not to_address:
        print("Transaction has no 'to' address (contract creation)")
        return

    to_checksum = Web3.to_checksum_address(to_address)
    print(f"Tx to: {to_checksum}")
    if to_checksum.lower() != CTF_CONTRACT_ADDRESS.lower():
        print("Transaction does not call the Conditional Tokens contract.")
        print("It likely transferred positions via the exchange; params not in tx input.")
        return

    contract = web3.eth.contract(address=CTF_CONTRACT_ADDRESS, abi=CTF_ABI)
    func, params = contract.decode_function_input(tx["input"])
    print(f"Decoded function: {func.fn_name}")
    for key, value in params.items():
        print(f"  {key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Try to extract redeem params from a tx or activity."
    )
    parser.add_argument(
        "token_or_tx",
        help="Token/condition id to search activity, or tx hash prefixed with 0x",
    )
    parser.add_argument(
        "--tx-hash",
        help="Explicit tx hash to decode",
    )
    args = parser.parse_args()

    # Reads a tx and decodes input if it's a direct CTF call.
    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not web3.is_connected():
        raise SystemExit("RPC connection failed.")

    tx_hash = args.tx_hash
    if not tx_hash:
        if args.token_or_tx.startswith("0x") and len(args.token_or_tx) > 40:
            tx_hash = args.token_or_tx
        else:
            tx_hash = _find_trade_tx(args.token_or_tx)
            if not tx_hash:
                print("No matching trade activity found.")
                return

    print(f"Using tx hash: {tx_hash}")
    _decode_ctf_tx(web3, tx_hash)


if __name__ == "__main__":
    main()
