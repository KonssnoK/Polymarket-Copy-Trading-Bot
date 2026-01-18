"""Decode CTF calls from a callTracer JSON blob (no RPC required).

Flow (debug redeem):
1) Grab trade tx hash with get_trade_tx_for_position_to_debug_traceTransaction.py
2) Use Alchemy's debug_traceTransaction (callTracer) and copy JSON output
3) Run this script to extract collateral/parent/condition/indexSets
4) Redeem with redeem_position_by_id.py using those params
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from web3 import Web3

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


def _walk_calls(node: dict, matches: list[dict]) -> None:
    if not isinstance(node, dict):
        return
    to_addr = node.get("to")
    if isinstance(to_addr, str) and to_addr.lower() == CTF_CONTRACT_ADDRESS.lower():
        matches.append(node)
    for child in node.get("calls", []) or []:
        _walk_calls(child, matches)


def _load_trace(trace_path: str | None, trace_json: str | None) -> dict:
    if trace_json:
        return json.loads(trace_json)
    if not trace_path:
        raise ValueError("Provide --trace-file or --trace-json.")
    return json.loads(Path(trace_path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse callTracer JSON and decode Conditional Tokens calls."
    )
    parser.add_argument("--trace-file", help="Path to callTracer JSON output")
    parser.add_argument("--trace-json", help="Raw JSON string")
    args = parser.parse_args()

    trace = _load_trace(args.trace_file, args.trace_json)
    if "result" in trace:
        trace = trace["result"]

    matches: list[dict] = []
    _walk_calls(trace, matches)
    if not matches:
        print("No CTF calls found in trace.")
        return

    contract = Web3().eth.contract(address=CTF_CONTRACT_ADDRESS, abi=CTF_ABI)
    print(f"Found {len(matches)} CTF call(s):")
    for idx, call in enumerate(matches, start=1):
        input_data = call.get("input")
        print(f"\nCTF Call {idx}:")
        if not input_data or input_data == "0x":
            print("  No input data.")
            continue
        try:
            func, params = contract.decode_function_input(input_data)
            print(f"  Function: {func.fn_name}")
            for key, value in params.items():
                print(f"    {key}: {value}")
        except Exception as exc:  # noqa: BLE001
            print(f"  Failed to decode input: {exc}")


if __name__ == "__main__":
    main()
