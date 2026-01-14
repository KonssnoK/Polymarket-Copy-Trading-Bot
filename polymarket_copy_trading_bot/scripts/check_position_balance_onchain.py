"""Check on-chain conditional token balance for a position token id."""

from __future__ import annotations

import argparse

import requests
from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

RPC_URL = ENV.rpc_url or "https://polygon-rpc.com"
PROXY_WALLET = ENV.proxy_wallet

CTF_CONTRACT_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CLOB_HTTP_URL = ENV.clob_http_url

CTF_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "id", "type": "uint256"},
        ],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
    ,
    {
        "inputs": [{"internalType": "bytes32", "name": "conditionId", "type": "bytes32"}],
        "name": "getOutcomeSlotCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "conditionId", "type": "bytes32"}],
        "name": "payoutDenominator",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "conditionId", "type": "bytes32"},
            {"internalType": "uint256", "name": "outcomeIndex", "type": "uint256"},
        ],
        "name": "payoutNumerators",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def _parse_token_id(raw: str) -> int:
    if raw.startswith("0x"):
        return int(raw, 16)
    return int(raw)


def _to_bytes32(condition_id: str) -> bytes:
    if condition_id.startswith("0x"):
        raw = Web3.to_bytes(hexstr=condition_id)
    else:
        raw = int(condition_id).to_bytes(32, byteorder="big")
    return raw.rjust(32, b"\x00")


def _lookup_position(wallet: str, token_id: int) -> dict | None:
    positions = fetch_data(f"https://data-api.polymarket.com/positions?user={wallet}")
    if not isinstance(positions, list):
        return None
    token_str = str(token_id)
    for pos in positions:
        if str(pos.get("asset") or "") == token_str:
            return pos
    return None


def _derive_index_set(position: dict) -> int | None:
    raw = position.get("indexSet") or position.get("indexSetHex")
    if raw is not None:
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str):
            try:
                return int(raw, 16) if raw.startswith("0x") else int(raw)
            except ValueError:
                return None
    outcome_index = position.get("outcomeIndex")
    if outcome_index is None:
        return None
    try:
        idx = int(outcome_index)
    except (TypeError, ValueError):
        return None
    return 1 << idx


def _derive_token_id(parent_collection: bytes, condition_id: str, index_set: int) -> int:
    condition_bytes = _to_bytes32(condition_id)
    collection_id = Web3.solidity_keccak(
        ["bytes32", "bytes32", "uint256"],
        [parent_collection, condition_bytes, index_set],
    )
    token_id_bytes = Web3.solidity_keccak(
        ["address", "bytes32"],
        [USDC_ADDRESS, collection_id],
    )
    return int.from_bytes(token_id_bytes, byteorder="big")


def _fetch_clob_market(condition_id: str) -> dict | None:
    if not CLOB_HTTP_URL:
        return None
    url = f"{CLOB_HTTP_URL.rstrip('/')}/markets/{condition_id}"
    try:
        response = requests.get(url, timeout=ENV.request_timeout_ms / 1000.0)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] CLOB market fetch failed for {url}: {exc}")
        return None


def _candidate_parent_collections(market: dict) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for key in (
        "neg_risk_market_id",
        "neg_risk_request_id",
        "question_id",
        "condition_id",
    ):
        value = market.get(key)
        if isinstance(value, str) and value:
            candidates.append((key, value))
    return candidates


def _candidate_condition_ids(position: dict, market: dict | None) -> list[str]:
    candidates: list[str] = []
    base = position.get("conditionId")
    if isinstance(base, str) and base:
        candidates.append(base)
    if market:
        for _, value in _candidate_parent_collections(market):
            if value not in candidates:
                candidates.append(value)
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check on-chain conditional token balance for a token id."
    )
    parser.add_argument("token_id", help="Token id (decimal or hex)")
    parser.add_argument(
        "--wallet",
        default=PROXY_WALLET,
        help="Wallet address to check (defaults to ENV.proxy_wallet)",
    )
    parser.add_argument(
        "--condition-id",
        help="Optional condition id to check on-chain resolution status",
    )
    args = parser.parse_args()

    token_id = _parse_token_id(args.token_id)
    wallet = args.wallet

    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not web3.is_connected():
        raise SystemExit("RPC connection failed.")

    contract = web3.eth.contract(address=CTF_CONTRACT_ADDRESS, abi=CTF_ABI)
    balance = contract.functions.balanceOf(wallet, token_id).call()

    print(f"Wallet: {wallet}")
    print(f"Token ID: {token_id}")
    print(f"CTF Contract: {CTF_CONTRACT_ADDRESS}")
    print(f"Balance (raw): {balance}")

    condition_id = args.condition_id
    position = None
    if not condition_id:
        position = _lookup_position(wallet, token_id)
        if position:
            condition_id = position.get("conditionId")
            if isinstance(condition_id, str) and condition_id:
                print(f"Condition ID (from positions API): {condition_id}")
            else:
                condition_id = None
    if position:
        print("Position fields (from positions API):")
        for key in (
            "conditionId",
            "outcomeIndex",
            "indexSet",
            "indexSetHex",
            "parentCollectionId",
            "parentCollection",
            "parentCollectionIdHex",
            "collectionId",
            "negativeRisk",
        ):
            if key in position:
                print(f"  {key}: {position.get(key)}")
        index_set = _derive_index_set(position)
        if condition_id and index_set is not None:
            derived_token_id = _derive_token_id(b"\x00" * 32, condition_id, index_set)
            matches = derived_token_id == token_id
            print(
                "Derived token id (parentCollection=0x00..00, "
                f"indexSet={index_set}): {derived_token_id}"
            )
            print(f"Derived token id matches asset: {matches}")
            alt_index_set = 2 if index_set == 1 else 1
            alt_token_id = _derive_token_id(b"\x00" * 32, condition_id, alt_index_set)
            alt_matches = alt_token_id == token_id
            print(
                "Derived token id (parentCollection=0x00..00, "
                f"indexSet={alt_index_set}): {alt_token_id}"
            )
            print(f"Derived token id matches asset (alt): {alt_matches}")
        if condition_id:
            market = _fetch_clob_market(condition_id)
            if market:
                print("CLOB market candidates for parent collection:")
                candidates = _candidate_parent_collections(market)
                if not candidates:
                    print("  (none found)")
                for key, value in candidates:
                    parent_bytes = _to_bytes32(value)
                    if index_set is not None:
                        derived = _derive_token_id(parent_bytes, condition_id, index_set)
                        print(f"  {key}: {value} -> token_id={derived} match={derived == token_id}")
                    else:
                        derived_one = _derive_token_id(parent_bytes, condition_id, 1)
                        derived_two = _derive_token_id(parent_bytes, condition_id, 2)
                        print(
                            f"  {key}: {value} -> token_id[1]={derived_one} match={derived_one == token_id}"
                        )
                        print(
                            f"  {key}: {value} -> token_id[2]={derived_two} match={derived_two == token_id}"
                        )
                print("Brute matching condition/parent combos:")
                condition_candidates = _candidate_condition_ids(position, market)
                parent_candidates = [b"\x00" * 32] + [
                    _to_bytes32(value) for _, value in candidates
                ]
                for cond in condition_candidates:
                    for parent in parent_candidates:
                        for candidate_index_set in (index_set, 1, 2):
                            if candidate_index_set is None:
                                continue
                            derived = _derive_token_id(parent, cond, candidate_index_set)
                            if derived == token_id:
                                print(
                                    f"  MATCH: condition_id={cond}, parent=0x{parent.hex()}, indexSet={candidate_index_set}"
                                )

    if condition_id:
        condition_bytes = _to_bytes32(condition_id)
        slot_count = contract.functions.getOutcomeSlotCount(condition_bytes).call()
        denominator = contract.functions.payoutDenominator(condition_bytes).call()

        print(f"Condition ID: {condition_id}")
        print(f"Outcome slots: {slot_count}")
        print(f"Payout denominator: {denominator}")

        numerators: list[int] = []
        for idx in range(int(slot_count)):
            numerator = contract.functions.payoutNumerators(condition_bytes, idx).call()
            numerators.append(int(numerator))
            print(f"Payout numerator[{idx}]: {numerator}")

        resolved = denominator > 0 and any(n > 0 for n in numerators)
        print(f"Resolved on-chain: {resolved}")
        if resolved:
            winners = [i for i, n in enumerate(numerators) if n > 0]
            print(f"Winning outcome indices: {winners}")


if __name__ == "__main__":
    main()
