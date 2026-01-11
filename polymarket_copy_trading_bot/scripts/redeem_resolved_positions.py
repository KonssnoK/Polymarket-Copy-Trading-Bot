"""Redeem resolved positions via Conditional Tokens contract."""

from __future__ import annotations

from typing import Iterable

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet
PRIVATE_KEY = ENV.private_key
RPC_URL = ENV.rpc_url or "https://polygon-rpc.com"

CTF_CONTRACT_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

RESOLVED_HIGH = 0.99
RESOLVED_LOW = 0.01
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


def _load_positions(address: str) -> list[dict]:
    data = fetch_data(f"https://data-api.polymarket.com/positions?user={address}")
    positions = data if isinstance(data, list) else []
    return [p for p in positions if float(p.get("size") or 0) > ZERO_THRESHOLD]


def _to_bytes32(condition_id: str) -> bytes:
    if condition_id.startswith("0x"):
        raw = Web3.to_bytes(hexstr=condition_id)
    else:
        raw = int(condition_id).to_bytes(32, byteorder="big")
    return raw.rjust(32, b"\x00")


def _redeem_position(web3: Web3, contract, condition_id: str) -> bool:
    try:
        condition_bytes = _to_bytes32(condition_id)
        parent_collection = b"\x00" * 32
        index_sets = [1, 2]

        tx = contract.functions.redeemPositions(
            USDC_ADDRESS,
            parent_collection,
            condition_bytes,
            index_sets,
        ).build_transaction(
            {
                "from": web3.eth.default_account,
                "nonce": web3.eth.get_transaction_count(web3.eth.default_account, "pending"),
                "gas": 500000,
                "gasPrice": web3.eth.gas_price,
            }
        )

        signed = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  Transaction submitted: {tx_hash.hex()}")
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status == 1:
            print("  Redemption successful")
            return True
        print("  Transaction failed")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  Redemption failed: {exc}")
        return False


def main() -> None:
    print("Redeeming resolved positions")
    print(f"Wallet: {PROXY_WALLET}")
    print(f"CTF Contract: {CTF_CONTRACT_ADDRESS}")
    print(f"Win threshold: price >= ${RESOLVED_HIGH}")
    print(f"Loss threshold: price <= ${RESOLVED_LOW}")

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

    all_positions = _load_positions(PROXY_WALLET)
    if not all_positions:
        print("No open positions detected for proxy wallet.")
        return

    redeemable_positions = [
        p
        for p in all_positions
        if (
            (float(p.get("curPrice") or 0) >= RESOLVED_HIGH
            or float(p.get("curPrice") or 0) <= RESOLVED_LOW)
            and p.get("redeemable") is True
        )
    ]

    active_positions = [
        p
        for p in all_positions
        if RESOLVED_LOW < float(p.get("curPrice") or 0) < RESOLVED_HIGH
    ]

    print("\nPosition statistics:")
    print(f"  Total positions: {len(all_positions)}")
    print(f"  Resolved and redeemable: {len(redeemable_positions)}")
    print(f"  Active (not touching): {len(active_positions)}")

    if not redeemable_positions:
        print("No positions to redeem.")
        return

    print(f"\nRedeeming {len(redeemable_positions)} positions...")
    print("WARNING: Each redemption requires gas fees on Polygon")

    positions_by_condition: dict[str, list[dict]] = {}
    for pos in redeemable_positions:
        positions_by_condition.setdefault(pos.get("conditionId"), []).append(pos)

    print(f"Grouped into {len(positions_by_condition)} unique conditions")

    success_count = 0
    fail_count = 0
    total_value = 0.0

    for idx, (condition_id, positions) in enumerate(positions_by_condition.items(), start=1):
        condition_value = sum(float(p.get("currentValue") or 0) for p in positions)
        print("\n" + "=" * 60)
        print(f"Condition {idx}/{len(positions_by_condition)}")
        print(f"Condition ID: {condition_id}")
        print(f"Positions in this condition: {len(positions)}")
        print(f"Total expected value: ${condition_value:.2f}")

        for pos in positions:
            status = "WIN" if float(pos.get("curPrice") or 0) >= RESOLVED_HIGH else "LOSS"
            print(
                f"  {status} {pos.get('title') or pos.get('slug')} | {pos.get('outcome')} | {float(pos.get('size') or 0):.2f} tokens | ${float(pos.get('currentValue') or 0):.2f}"
            )

        if _redeem_position(web3, contract, condition_id):
            success_count += 1
            total_value += condition_value
        else:
            fail_count += 1

    print("\nSummary of position redemption")
    print(f"Conditions processed: {len(positions_by_condition)}")
    print(f"Successful redemptions: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Expected value of redeemed positions: ${total_value:.2f}")


if __name__ == "__main__":
    main()
