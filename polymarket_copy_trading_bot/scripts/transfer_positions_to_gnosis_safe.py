"""Transfer positions from EOA to Gnosis Safe."""

from __future__ import annotations

import time

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PRIVATE_KEY = ENV.private_key
RPC_URL = ENV.rpc_url

EOA_ADDRESS = "0x4fbBe5599c06e846D2742014c9eB04A8a3d1DE8C"
GNOSIS_SAFE_ADDRESS = "0xd62531bc536bff72394fc5ef715525575787e809"
CONDITIONAL_TOKENS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

ERC1155_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "id", "type": "uint256"},
            {"name": "amount", "type": "uint256"},
            {"name": "data", "type": "bytes"},
        ],
        "name": "safeTransferFrom",
        "outputs": [],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "id", "type": "uint256"},
        ],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "operator", "type": "address"},
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"},
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "type": "function",
    },
]

def _parse_token_id(token_id: str) -> int:
    if isinstance(token_id, str) and token_id.startswith("0x"):
        return int(token_id, 16)
    return int(token_id)


def main() -> None:
    print("Transfer positions from EOA to Gnosis Safe\n")
    print(f"FROM (EOA):       {EOA_ADDRESS}")
    print(f"TO (Gnosis Safe): {GNOSIS_SAFE_ADDRESS}\n")

    positions = fetch_data(
        f"https://data-api.polymarket.com/positions?user={EOA_ADDRESS}"
    ) or []

    if not positions:
        print("No positions found in EOA")
        return

    total_value = sum(float(p.get("currentValue") or 0) for p in positions)
    print(f"Found positions: {len(positions)}")
    print(f"Total value (estimated): ${total_value:.2f}\n")

    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    account = web3.eth.account.from_key(PRIVATE_KEY)

    print("Connected to Polygon")
    print(f"Wallet: {account.address}\n")

    if account.address.lower() != EOA_ADDRESS.lower():
        print("Error: signer does not match EOA address.")
        print(f"Expected: {EOA_ADDRESS}")
        print(f"Signer:   {account.address}")
        return

    contract = web3.eth.contract(address=CONDITIONAL_TOKENS, abi=ERC1155_ABI)

    success_count = 0
    failure_count = 0

    for idx, pos in enumerate(positions, start=1):
        print(f"\nPosition {idx}/{len(positions)}")
        print(f"Market: {pos.get('title') or 'Unknown'}")
        print(f"Outcome: {pos.get('outcome') or 'Unknown'}")
        print(f"Size: {float(pos.get('size') or 0):.2f} shares")
        print(f"Value: ${float(pos.get('currentValue') or 0):.2f}")
        print(f"Token ID: {str(pos.get('asset'))[:20]}...")

        try:
            token_id = _parse_token_id(str(pos.get("asset")))
            balance = contract.functions.balanceOf(EOA_ADDRESS, token_id).call()
            print(f"Balance in EOA: {balance} tokens")
            if balance == 0:
                print("Skipping: no balance for this token")
                failure_count += 1
                continue

            gas_price = int(web3.eth.gas_price * 1.5)

            is_approved = contract.functions.isApprovedForAll(
                EOA_ADDRESS, GNOSIS_SAFE_ADDRESS
            ).call()
            if not is_approved:
                print("Setting approval for Gnosis Safe...")
                tx = contract.functions.setApprovalForAll(
                    GNOSIS_SAFE_ADDRESS, True
                ).build_transaction(
                    {
                        "from": EOA_ADDRESS,
                        "nonce": web3.eth.get_transaction_count(EOA_ADDRESS),
                        "gas": 100000,
                        "gasPrice": gas_price,
                    }
                )
                signed = account.sign_transaction(tx)
                tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
                web3.eth.wait_for_transaction_receipt(tx_hash)
                print("Approval set\n")

            print(f"Transferring {balance} tokens...")
            tx = contract.functions.safeTransferFrom(
                EOA_ADDRESS, GNOSIS_SAFE_ADDRESS, token_id, balance, b""
            ).build_transaction(
                {
                    "from": EOA_ADDRESS,
                    "nonce": web3.eth.get_transaction_count(EOA_ADDRESS),
                    "gas": 200000,
                    "gasPrice": gas_price,
                }
            )
            signed = account.sign_transaction(tx)
            tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"Transfer confirmed in block {receipt.blockNumber}")
            success_count += 1

            if idx < len(positions):
                print("Waiting 3 seconds...")
                time.sleep(3)
        except Exception as exc:  # noqa: BLE001
            print(f"Transfer failed: {exc}")
            failure_count += 1

    print("\nTransfer summary")
    print(f"Successful transfers: {success_count}/{len(positions)}")
    print(f"Failed: {failure_count}/{len(positions)}")

    time.sleep(5)
    eoa_positions_after = fetch_data(
        f"https://data-api.polymarket.com/positions?user={EOA_ADDRESS}"
    ) or []
    safe_positions_after = fetch_data(
        f"https://data-api.polymarket.com/positions?user={GNOSIS_SAFE_ADDRESS}"
    ) or []

    print("\nTransfer results:")
    print(f"  EOA:         {len(eoa_positions_after)} positions")
    print(f"  Gnosis Safe: {len(safe_positions_after)} positions")

    if safe_positions_after:
        print("Positions appear in Gnosis Safe profile:")
        print(f"  https://polymarket.com/profile/{GNOSIS_SAFE_ADDRESS}")
    else:
        print(
            "API may take time to reflect the move. Refresh later or verify on-chain."
        )


if __name__ == "__main__":
    main()
