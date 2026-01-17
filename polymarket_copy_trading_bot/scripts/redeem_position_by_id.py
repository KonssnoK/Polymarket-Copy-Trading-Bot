"""Redeem one or more positions by ID (index, token id, or condition id)."""

from __future__ import annotations

import argparse

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet
PRIVATE_KEY = ENV.private_key
RPC_URL = ENV.rpc_url or "https://polygon-rpc.com"

CTF_CONTRACT_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

ZERO_THRESHOLD = 0.0001

CTF_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSets", "type": "uint256[]"},
        ],
        "name": "redeemPositions",
        "outputs": [],
        "type": "function",
    }
]


def _load_positions() -> list[dict]:
    positions = fetch_data(
        f"https://data-api.polymarket.com/positions?user={PROXY_WALLET}"
    )
    if not isinstance(positions, list):
        return []
    return [p for p in positions if float(p.get("size") or 0) > ZERO_THRESHOLD]


def _sort_positions(positions: list[dict]) -> list[dict]:
    return sorted(
        positions, key=lambda p: float(p.get("currentValue") or 0), reverse=True
    )


def _find_position(sorted_positions: list[dict], position_id: str) -> dict | None:
    if position_id.isdigit():
        index = int(position_id)
        if 1 <= index <= len(sorted_positions):
            return sorted_positions[index - 1]
        return None

    for pos in sorted_positions:
        if pos.get("asset") == position_id:
            return pos
        if pos.get("conditionId") == position_id:
            return pos
    return None


def _to_bytes32(condition_id: str) -> bytes:
    if condition_id.startswith("0x"):
        raw = Web3.to_bytes(hexstr=condition_id)
    else:
        raw = int(condition_id).to_bytes(32, byteorder="big")
    return raw.rjust(32, b"\x00")


def _redeem_condition(
    web3: Web3,
    contract,
    condition_id: str,
    gas_multiplier: float,
    wait_seconds: int,
    nonce_override: int | None,
) -> bool:
    try:
        condition_bytes = _to_bytes32(condition_id)
        parent_collection = b"\x00" * 32
        index_sets = [1, 2]

        base_gas_price = web3.eth.gas_price
        gas_price = int(base_gas_price * gas_multiplier)
        nonce = (
            nonce_override
            if nonce_override is not None
            else web3.eth.get_transaction_count(web3.eth.default_account, "pending")
        )
        tx = contract.functions.redeemPositions(
            USDC_ADDRESS,
            parent_collection,
            condition_bytes,
            index_sets,
        ).build_transaction(
            {
                "from": web3.eth.default_account,
                "nonce": nonce,
                "gas": 500000,
                "gasPrice": gas_price,
            }
        )

        signed = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
        if gas_multiplier != 1.0 or nonce_override is not None:
            print(
                "  Gas price: "
                f"{gas_price} wei (multiplier {gas_multiplier}x from {base_gas_price})"
            )
        if nonce_override is not None:
            print(f"  Nonce override: {nonce_override}")
        print(f"  Transaction submitted: {tx_hash.hex()}")
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=wait_seconds)
        if receipt.status == 1:
            print("  Redemption successful")
            return True
        print("  Transaction failed")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  Redemption failed: {exc}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Redeem positions by ID.")
    parser.add_argument(
        "position_ids",
        nargs="+",
        help="Numeric IDs from get_positions_ids.py/get_redeemable_ids.py or token/condition ids",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Attempt redemption even if position is not marked redeemable",
    )
    parser.add_argument(
        "--gas-multiplier",
        type=float,
        default=1.0,
        help="Multiply the current gas price to speed up confirmations (default: 1.0)",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=120,
        help="How long to wait for confirmation before timing out (default: 120)",
    )
    parser.add_argument(
        "--nonce",
        type=int,
        default=None,
        help="Override the nonce to replace a pending transaction",
    )
    args = parser.parse_args()

    positions = _load_positions()
    if not positions:
        print("No open positions")
        return

    sorted_positions = _sort_positions(positions)
    selected: list[dict] = []
    for pid in args.position_ids:
        pos = _find_position(sorted_positions, pid)
        if not pos:
            print(f"Position not found: {pid}")
            continue
        selected.append(pos)

    if not selected:
        print("No valid positions selected.")
        return

    positions_by_condition: dict[str, list[dict]] = {}
    for pos in selected:
        condition_id = pos.get("conditionId")
        if not condition_id:
            print(f"Position missing condition id: {pos.get('asset')}")
            continue
        positions_by_condition.setdefault(str(condition_id), []).append(pos)

    if not positions_by_condition:
        print("No valid conditions selected.")
        return

    print("Positions selected:")
    for condition_id, condition_positions in positions_by_condition.items():
        print("-" * 50)
        print(f"Condition ID: {condition_id}")
        for pos in condition_positions:
            print(f"  Token ID: {pos.get('asset')}")
            print(
                f"    {pos.get('title') or pos.get('slug')} | {pos.get('outcome')} | {float(pos.get('size') or 0):.2f} tokens"
            )
            if not pos.get("redeemable") and not args.force:
                print("    Not marked redeemable; will be skipped")

    if not args.yes:
        confirm = input("Redeem these positions? Type 'yes' to confirm: ").strip().lower()
        if confirm != "yes":
            print("Cancelled.")
            return

    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    account = web3.eth.account.from_key(PRIVATE_KEY)
    web3.eth.default_account = account.address

    print("Connected to Polygon RPC")
    print(f"Signer address: {account.address}")

    if account.address.lower() != PROXY_WALLET.lower():
        print(
            f"Note: signer ({account.address}) differs from proxy wallet ({PROXY_WALLET})."
        )
        print("Make sure signer has permission to execute transactions on proxy wallet.")

    contract = web3.eth.contract(address=CTF_CONTRACT_ADDRESS, abi=CTF_ABI)

    success_count = 0
    fail_count = 0

    for condition_id, condition_positions in positions_by_condition.items():
        redeemable = [
            pos for pos in condition_positions if pos.get("redeemable") or args.force
        ]
        if not redeemable:
            print("-" * 50)
            print(f"Skipping condition {condition_id}: not redeemable")
            continue

        print("-" * 50)
        print(f"Redeeming condition {condition_id} ({len(redeemable)} position(s))")
        if _redeem_condition(
            web3,
            contract,
            condition_id,
            args.gas_multiplier,
            args.wait_seconds,
            args.nonce,
        ):
            success_count += 1
        else:
            fail_count += 1

    print("\nSummary")
    print(f"Conditions processed: {len(positions_by_condition)}")
    print(f"Successful redemptions: {success_count}")
    print(f"Failed: {fail_count}")


if __name__ == "__main__":
    main()
