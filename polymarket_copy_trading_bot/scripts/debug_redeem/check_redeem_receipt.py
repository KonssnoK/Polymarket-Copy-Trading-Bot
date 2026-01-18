"""Inspect a redemption tx receipt for CTF burn events.

Use this after a redeem tx to verify the Conditional Tokens burn happened.
If no burn logs are found, the redemption likely used wrong params.
"""

from __future__ import annotations

import argparse

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV

RPC_URL = ENV.rpc_url or "https://polygon-rpc.com"
CTF_CONTRACT_ADDRESS = Web3.to_checksum_address(
    "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
)

TRANSFER_SINGLE_TOPIC = Web3.keccak(
    text="TransferSingle(address,address,address,uint256,uint256)"
).hex()
TRANSFER_BATCH_TOPIC = Web3.keccak(
    text="TransferBatch(address,address,address,uint256[],uint256[])"
).hex()


def _normalize_hash(tx_hash: str) -> str:
    return tx_hash if tx_hash.startswith("0x") else f"0x{tx_hash}"


def _decode_transfer_single(data_hex: str) -> tuple[int, int]:
    raw = Web3.to_bytes(hexstr=data_hex)
    if len(raw) < 64:
        return 0, 0
    token_id = int.from_bytes(raw[0:32], byteorder="big")
    value = int.from_bytes(raw[32:64], byteorder="big")
    return token_id, value


def _decode_batch(data_hex: str) -> tuple[list[int], list[int]]:
    raw = Web3.to_bytes(hexstr=data_hex)
    if len(raw) < 64:
        return [], []
    ids_offset = int.from_bytes(raw[0:32], byteorder="big")
    values_offset = int.from_bytes(raw[32:64], byteorder="big")
    ids_start = ids_offset
    values_start = values_offset
    ids_len = int.from_bytes(raw[ids_start : ids_start + 32], byteorder="big")
    ids = []
    cursor = ids_start + 32
    for _ in range(ids_len):
        ids.append(int.from_bytes(raw[cursor : cursor + 32], byteorder="big"))
        cursor += 32
    values_len = int.from_bytes(raw[values_start : values_start + 32], byteorder="big")
    values = []
    cursor = values_start + 32
    for _ in range(values_len):
        values.append(int.from_bytes(raw[cursor : cursor + 32], byteorder="big"))
        cursor += 32
    return ids, values


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check a CTF redemption tx receipt for burn events."
    )
    parser.add_argument("tx_hash", help="Transaction hash (with or without 0x)")
    parser.add_argument(
        "--token-id",
        help="Optional token id to filter for",
    )
    args = parser.parse_args()

    # Read receipt directly from Polygon RPC; no special provider required.
    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not web3.is_connected():
        raise SystemExit("RPC connection failed.")

    tx_hash = _normalize_hash(args.tx_hash)
    receipt = web3.eth.get_transaction_receipt(tx_hash)
    if receipt is None:
        print(f"Receipt not found for {tx_hash}")
        return

    token_filter = int(args.token_id) if args.token_id else None

    print(f"Tx hash: {tx_hash}")
    print(f"Status: {'success' if receipt.status == 1 else 'failed'}")
    print(f"Logs: {len(receipt.logs)}")

    matches = 0
    for log in receipt.logs:
        if log.address.lower() != CTF_CONTRACT_ADDRESS.lower():
            continue
        if not log.topics:
            continue
        topic0 = log.topics[0].hex()
        if topic0 == TRANSFER_SINGLE_TOPIC:
            token_id, value = _decode_transfer_single(log.data)
            if token_filter is None or token_id == token_filter:
                matches += 1
                print(
                    f"TransferSingle token_id={token_id} value={value} from={log.topics[2].hex()} to={log.topics[3].hex()}"
                )
        elif topic0 == TRANSFER_BATCH_TOPIC:
            ids, values = _decode_batch(log.data)
            for token_id, value in zip(ids, values):
                if token_filter is None or token_id == token_filter:
                    matches += 1
                    print(f"TransferBatch token_id={token_id} value={value}")

    if matches == 0:
        print("No matching CTF transfer logs found.")


if __name__ == "__main__":
    main()
