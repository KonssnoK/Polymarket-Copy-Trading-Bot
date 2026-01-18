"""Redeem one or more positions by ID (index, token id, or condition id)."""

from __future__ import annotations

import argparse

import requests
from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PROXY_WALLET = ENV.proxy_wallet
PRIVATE_KEY = ENV.private_key
RPC_URL = ENV.rpc_url or "https://polygon-rpc.com"
CLOB_HTTP_URL = ENV.clob_http_url

CTF_CONTRACT_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
USDC_NATIVE_ADDRESS = "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"
NEG_RISK_COLLATERAL = "0x3a3bd7bb9528e159577f7c2e685cc81a765002e2"

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
    if position_id.isdigit() and len(position_id) <= 4:
        index = int(position_id)
        if 1 <= index <= len(sorted_positions):
            return sorted_positions[index - 1]
        return None

    for pos in sorted_positions:
        if str(pos.get("asset") or "") == str(position_id):
            return pos
        if str(pos.get("conditionId") or "") == str(position_id):
            return pos
    return None


def _to_bytes32(condition_id: str) -> bytes:
    if condition_id.startswith("0x"):
        raw = Web3.to_bytes(hexstr=condition_id)
    else:
        raw = int(condition_id).to_bytes(32, byteorder="big")
    return raw.rjust(32, b"\x00")


def _parse_hex_or_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text, 16) if text.startswith("0x") else int(text)
        except ValueError:
            return None
    return None


def _derive_index_set(position: dict) -> int | None:
    raw = position.get("indexSet") or position.get("indexSetHex")
    parsed = _parse_hex_or_int(raw)
    if parsed is not None:
        return parsed
    outcome_index = _parse_hex_or_int(position.get("outcomeIndex"))
    if outcome_index is None:
        return None
    return 1 << outcome_index


def _fetch_clob_market(condition_id: str) -> dict | None:
    if not CLOB_HTTP_URL:
        return None
    url = f"{CLOB_HTTP_URL.rstrip('/')}/markets/{condition_id}"
    try:
        response = requests.get(url, timeout=ENV.request_timeout_ms / 1000.0)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _candidate_parent_collections(position: dict) -> list[tuple[bytes, str]]:
    candidates: list[tuple[bytes, str]] = []
    for key in (
        "parentCollectionId",
        "parentCollectionIdHex",
        "parentCollection",
        "parentCollectionHex",
    ):
        raw = position.get(key)
        if isinstance(raw, str) and raw:
            candidates.append((_to_bytes32(raw), f"position.{key}"))
        parsed = _parse_hex_or_int(raw)
        if parsed is not None:
            candidates.append((parsed.to_bytes(32, byteorder="big"), f"position.{key}"))

    if position.get("negativeRisk"):
        condition_id = position.get("conditionId")
        if isinstance(condition_id, str) and condition_id:
            market = _fetch_clob_market(condition_id)
            if market:
                for key in ("neg_risk_market_id", "neg_risk_request_id", "question_id"):
                    value = market.get(key)
                    if isinstance(value, str) and value:
                        candidates.append((_to_bytes32(value), f"clob.{key}"))

    candidates.append((b"\x00" * 32, "default.zero"))
    return candidates


def _resolve_redeem_params(
    position: dict,
) -> tuple[str | None, list[tuple[bytes, str]], int | None]:
    condition_id = position.get("conditionId")
    if not isinstance(condition_id, str) or not condition_id:
        return None, [], None
    parent_collections = _candidate_parent_collections(position)
    index_set = _derive_index_set(position)
    return condition_id, parent_collections, index_set


def _parse_parent_collection(value: str) -> bytes:
    text = value.strip()
    if not text:
        raise ValueError("parent collection cannot be empty")
    if text.startswith("0x"):
        raw = Web3.to_bytes(hexstr=text)
    else:
        raw = int(text, 16).to_bytes(32, byteorder="big")
    return raw.rjust(32, b"\x00")


def _redeem_condition(
    web3: Web3,
    contract,
    collateral_token: str,
    condition_id: str,
    parent_collection: bytes,
    index_sets: list[int],
    gas_multiplier: float,
    wait_seconds: int,
    nonce_override: int | None,
    preflight: bool,
) -> bool:
    try:
        condition_bytes = _to_bytes32(condition_id)

        if preflight:
            try:
                contract.functions.redeemPositions(
                    Web3.to_checksum_address(collateral_token),
                    parent_collection,
                    condition_bytes,
                    index_sets,
                ).call({"from": web3.eth.default_account})
            except Exception as exc:  # noqa: BLE001
                print(f"  Preflight failed: {exc}")
                return False

        base_gas_price = web3.eth.gas_price
        gas_price = int(base_gas_price * gas_multiplier)
        nonce = (
            nonce_override
            if nonce_override is not None
            else web3.eth.get_transaction_count(web3.eth.default_account, "pending")
        )
        tx = contract.functions.redeemPositions(
            Web3.to_checksum_address(collateral_token),
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
        nargs="*",
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
    parser.add_argument(
        "--try-all-parents",
        action="store_true",
        help="Try multiple parent collection candidates until redeem succeeds",
    )
    parser.add_argument(
        "--parent-collection",
        help="Force a specific parent collection id (0x... bytes32 or hex)",
    )
    parser.add_argument(
        "--use-neg-risk-collateral",
        action="store_true",
        help="Use neg-risk collateral instead of USDC",
    )
    parser.add_argument(
        "--no-preflight",
        action="store_true",
        help="Skip the preflight eth_call check before sending transactions",
    )
    parser.add_argument(
        "--all-redeemable",
        action="store_true",
        help="Redeem all positions marked redeemable",
    )
    args = parser.parse_args()

    positions = _load_positions()
    if not positions:
        print("No open positions")
        return

    sorted_positions = _sort_positions(positions)
    selected: list[dict] = []
    if args.all_redeemable:
        selected = [pos for pos in sorted_positions if pos.get("redeemable")]
        if not selected:
            print("No redeemable positions found.")
            return
    else:
        if not args.position_ids:
            print("No positions selected.")
            return
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
    resolved_groups: dict[str, dict] = {}
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
            cond, parent_collections, index_set = _resolve_redeem_params(pos)
            if cond and parent_collections and index_set is not None:
                group = resolved_groups.setdefault(
                    cond,
                    {
                        "condition_id": cond,
                        "parent_candidates": parent_collections,
                        "index_sets": set(),
                    },
                )
                group["index_sets"].add(index_set)
            else:
                print("    Unable to resolve redeem params; will be skipped")

    if not args.yes:
        confirm = input("Redeem these positions? Type 'yes' to confirm: ").strip().lower()
        if confirm != "yes":
            print("Cancelled.")
            return

    if not resolved_groups:
        print("No redeemable positions with resolvable params.")
        return

    if args.nonce is not None and len(resolved_groups) > 1:
        print("Nonce override provided with multiple redemption groups.")
        print("Please redeem one group at a time when overriding nonce.")
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

    if args.use_neg_risk_collateral:
        collateral_candidates = [NEG_RISK_COLLATERAL]
    else:
        collateral_candidates = [USDC_ADDRESS, USDC_NATIVE_ADDRESS]

    for group in resolved_groups.values():
        condition_id = group["condition_id"]
        index_sets = sorted(group["index_sets"])
        print("-" * 50)
        print(f"Redeeming condition {condition_id}")
        print(f"  Index sets: {index_sets}")

        candidates = group["parent_candidates"]
        if args.use_neg_risk_collateral:
            candidates = [(b"\x00" * 32, "neg_risk.default_zero")]
        if args.parent_collection:
            try:
                forced = _parse_parent_collection(args.parent_collection)
            except ValueError as exc:
                print(f"Invalid --parent-collection: {exc}")
                return
            candidates = [(forced, "override.parent_collection")]
        if not args.try_all_parents:
            candidates = candidates[:1]
        for parent_collection, source in candidates:
            for collateral_token in collateral_candidates:
                print(f"  Parent collection: 0x{parent_collection.hex()} ({source})")
                print(f"  Collateral token: {collateral_token}")
                if _redeem_condition(
                    web3,
                    contract,
                    collateral_token,
                    condition_id,
                    parent_collection,
                    index_sets,
                    args.gas_multiplier,
                    args.wait_seconds,
                    args.nonce,
                    not args.no_preflight,
                ):
                    success_count += 1
                    break
            else:
                continue
            break
        else:
            fail_count += 1

    print("\nSummary")
    print(f"Conditions processed: {len(positions_by_condition)}")
    print(f"Successful redemptions: {success_count}")
    print(f"Failed: {fail_count}")


if __name__ == "__main__":
    main()
