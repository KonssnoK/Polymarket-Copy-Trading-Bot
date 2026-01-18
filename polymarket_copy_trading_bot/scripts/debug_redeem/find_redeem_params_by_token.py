"""Try to derive redeem parameters (condition, parent, indexSet) for a token id.

This is a fallback when traces aren't available. It brute-forces candidates
from positions + CLOB metadata and can be slow/noisy.
"""

from __future__ import annotations

import argparse

import requests
from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

RPC_URL = ENV.rpc_url or "https://polygon-rpc.com"
PROXY_WALLET = ENV.proxy_wallet
CLOB_HTTP_URL = ENV.clob_http_url

CTF_CONTRACT_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
USDC_NATIVE_ADDRESS = "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"

CTF_ABI = [
    {
        "inputs": [{"internalType": "bytes32", "name": "conditionId", "type": "bytes32"}],
        "name": "getOutcomeSlotCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]


def _parse_token_id(raw: str) -> int:
    if raw.startswith("0x"):
        return int(raw, 16)
    return int(raw)


def _to_bytes32(value: str) -> bytes:
    if value.startswith("0x"):
        raw = Web3.to_bytes(hexstr=value)
    else:
        raw = int(value).to_bytes(32, byteorder="big")
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


def _derive_token_id(
    collateral_token: str,
    parent_collection: bytes,
    condition_id: str,
    index_set: int,
) -> int:
    checksum_token = Web3.to_checksum_address(collateral_token)
    condition_bytes = _to_bytes32(condition_id)
    collection_id = Web3.solidity_keccak(
        ["bytes32", "bytes32", "uint256"],
        [parent_collection, condition_bytes, index_set],
    )
    token_id_bytes = Web3.solidity_keccak(
        ["address", "bytes32"],
        [checksum_token, collection_id],
    )
    return int.from_bytes(token_id_bytes, byteorder="big")


def _load_positions(wallet: str) -> list[dict]:
    data = fetch_data(f"https://data-api.polymarket.com/positions?user={wallet}")
    return data if isinstance(data, list) else []


def _find_position(positions: list[dict], token_id: int) -> dict | None:
    token_str = str(token_id)
    for pos in positions:
        if str(pos.get("asset") or "") == token_str:
            return pos
    return None


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


def _candidate_values_from_position(position: dict, keys: tuple[str, ...]) -> list[str]:
    candidates: list[str] = []
    for key in keys:
        raw = position.get(key)
        if isinstance(raw, str) and raw:
            candidates.append(raw)
        parsed = _parse_hex_or_int(raw)
        if parsed is not None:
            candidates.append(hex(parsed))
    return candidates


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find possible redeem params for a token id."
    )
    parser.add_argument("token_id", help="Token id (decimal or hex)")
    parser.add_argument(
        "--wallet",
        default=PROXY_WALLET,
        help="Wallet address to check (defaults to ENV.proxy_wallet)",
    )
    parser.add_argument(
        "--condition-id",
        help="Optional condition id override",
    )
    parser.add_argument(
        "--max-index",
        type=int,
        default=32,
        help="Max indexSet combinations to try when outcomeIndex is unknown",
    )
    parser.add_argument(
        "--force-index-bruteforce",
        action="store_true",
        help="Ignore outcomeIndex and brute-force indexSet values",
    )
    parser.add_argument(
        "--collateral-token",
        action="append",
        help="Additional collateral token address to test",
    )
    args = parser.parse_args()

    # This script is a brute-force helper; success is not guaranteed.
    token_id = _parse_token_id(args.token_id)

    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not web3.is_connected():
        raise SystemExit("RPC connection failed.")
    contract = web3.eth.contract(address=CTF_CONTRACT_ADDRESS, abi=CTF_ABI)

    positions = _load_positions(args.wallet)
    position = _find_position(positions, token_id)

    condition_candidates: list[str] = []
    parent_candidates: list[str] = []
    outcome_index = None
    collateral_candidates = [USDC_ADDRESS, USDC_NATIVE_ADDRESS]

    if position:
        outcome_index = _parse_hex_or_int(position.get("outcomeIndex"))
        condition_candidates.extend(
            _candidate_values_from_position(position, ("conditionId",))
        )
        parent_candidates.extend(
            _candidate_values_from_position(
                position,
                (
                    "parentCollectionId",
                    "parentCollectionIdHex",
                    "parentCollection",
                    "parentCollectionHex",
                ),
            )
        )
        for key in ("collateral", "collateralToken", "collateralTokenAddress"):
            value = position.get(key)
            if isinstance(value, str) and value.startswith("0x"):
                collateral_candidates.append(value)

    if args.condition_id:
        condition_candidates.append(args.condition_id)

    condition_candidates = _dedupe([c for c in condition_candidates if c])
    parent_candidates = _dedupe([c for c in parent_candidates if c])

    if condition_candidates:
        for cond in list(condition_candidates):
            market = _fetch_clob_market(cond)
            if not market:
                continue
            for key in ("condition_id", "question_id", "neg_risk_market_id", "neg_risk_request_id"):
                value = market.get(key)
                if isinstance(value, str) and value:
                    condition_candidates.append(value)
                    parent_candidates.append(value)
            break

    if args.collateral_token:
        collateral_candidates.extend(args.collateral_token)

    condition_candidates = _dedupe(condition_candidates)
    parent_candidates = _dedupe(parent_candidates)
    collateral_candidates = _dedupe([c for c in collateral_candidates if c])
    if "0x" + ("0" * 64) not in parent_candidates:
        parent_candidates.append("0x" + ("0" * 64))

    print(f"Token ID: {token_id}")
    print(f"Condition candidates: {len(condition_candidates)}")
    print(f"Parent candidates: {len(parent_candidates)}")
    print(f"Collateral candidates: {len(collateral_candidates)}")
    print(f"Outcome index: {outcome_index if outcome_index is not None else 'unknown'}")

    matches = 0
    for condition_id in condition_candidates:
        try:
            slot_count = contract.functions.getOutcomeSlotCount(_to_bytes32(condition_id)).call()
        except Exception:
            continue

        if outcome_index is not None and not args.force_index_bruteforce:
            index_sets = [1 << outcome_index]
        else:
            max_bits = min(int(slot_count), 5)
            max_index = min(args.max_index, (1 << max_bits) - 1)
            index_sets = list(range(1, max_index + 1))

        for parent_value in parent_candidates:
            parent_bytes = _to_bytes32(parent_value)
            for collateral in collateral_candidates:
                for index_set in index_sets:
                    derived = _derive_token_id(
                        collateral, parent_bytes, condition_id, index_set
                    )
                    if derived == token_id:
                        matches += 1
                        print("MATCH FOUND")
                        print(f"  condition_id: {condition_id}")
                        print(f"  parentCollectionId: 0x{parent_bytes.hex()}")
                        print(f"  indexSet: {index_set}")
                        print(f"  collateralToken: {collateral}")

    if matches == 0:
        print("No matches found.")


if __name__ == "__main__":
    main()
