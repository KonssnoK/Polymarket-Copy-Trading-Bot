"""Check USDC balance/allowance and optionally set approval."""

from __future__ import annotations

from typing import Any

from web3 import Web3

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import AssetType, BalanceAllowanceParams

from polymarket_copy_trading_bot.config.env import ENV

PROXY_WALLET = ENV.proxy_wallet
PRIVATE_KEY = ENV.private_key
RPC_URL = ENV.rpc_url
USDC_CONTRACT_ADDRESS = ENV.usdc_contract_address
CLOB_HTTP_URL = ENV.clob_http_url
POLYGON_CHAIN_ID = 137
POLYMARKET_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
NATIVE_USDC_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"

USDC_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
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


def _build_clob_client(web3: Web3) -> ClobClient:
    code = web3.eth.get_code(PROXY_WALLET)
    is_proxy_safe = code not in (b"", b"0x") and len(code) > 0
    signature_type = 2 if is_proxy_safe else 0

    client = ClobClient(
        CLOB_HTTP_URL,
        chain_id=POLYGON_CHAIN_ID,
        key=PRIVATE_KEY,
        signature_type=signature_type,
        funder=PROXY_WALLET,
    )

    try:
        client.set_api_creds(client.create_or_derive_api_creds())
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Failed to obtain Polymarket API credentials") from exc

    return client


def _sync_polymarket_allowance_cache(decimals: int, web3: Web3) -> None:
    try:
        print("Syncing Polymarket allowance cache...")
        clob_client = _build_clob_client(web3)
        update_params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)

        update_result = clob_client.update_balance_allowance(update_params)
        if isinstance(update_result, dict) and "error" in update_result:
            print(f"Polymarket cache update failed: {update_result['error']}")
            return
        print("Polymarket cache update acknowledged")

        balance_response = clob_client.get_balance_allowance(update_params)
        if not isinstance(balance_response, dict):
            print("Unexpected response from Polymarket for balance/allowance")
            return
        if "error" in balance_response:
            print(f"Unable to fetch Polymarket balance/allowance: {balance_response['error']}")
            return

        balance = balance_response.get("balance")
        allowance = balance_response.get("allowance")
        if balance is None or allowance is None:
            print("Polymarket did not provide balance/allowance data")
            return

        synced_balance = Web3.from_wei(int(balance), "mwei")
        synced_allowance = Web3.from_wei(int(allowance), "mwei")
        print(f"Polymarket Recorded Balance: {synced_balance} USDC")
        print(f"Polymarket Recorded Allowance: {synced_allowance} USDC\n")
    except Exception as exc:  # noqa: BLE001
        print(f"Unable to sync Polymarket cache: {exc}")


def main() -> None:
    print("Checking USDC balance and allowance...\n")

    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    account = web3.eth.account.from_key(PRIVATE_KEY)

    usdc_contract = web3.eth.contract(address=USDC_CONTRACT_ADDRESS, abi=USDC_ABI)

    decimals = usdc_contract.functions.decimals().call()
    print(f"USDC Decimals: {decimals}")

    local_balance = usdc_contract.functions.balanceOf(PROXY_WALLET).call()
    spender_addresses = [POLYMARKET_EXCHANGE, NEG_RISK_EXCHANGE, NEG_RISK_ADAPTER]

    local_balance_formatted = Web3.from_wei(local_balance, "mwei")
    print(f"Your USDC Balance ({USDC_CONTRACT_ADDRESS}): {local_balance_formatted} USDC")
    print("Checking allowance for Polymarket spenders:\n")

    max_allowance = (1 << 256) - 1
    gas_price = web3.eth.gas_price
    nonce = web3.eth.get_transaction_count(account.address, "pending")

    for spender in spender_addresses:
        local_allowance = usdc_contract.functions.allowance(PROXY_WALLET, spender).call()
        local_allowance_formatted = Web3.from_wei(local_allowance, "mwei")
        print(f"Spender: {spender}")
        print(f"  Allowance: {local_allowance_formatted} USDC")

        if int(local_allowance) < int(local_balance) or int(local_allowance) == 0:
            print("  Allowance insufficient; setting unlimited allowance...")
            tx = usdc_contract.functions.approve(spender, max_allowance).build_transaction(
                {
                    "from": account.address,
                    "nonce": nonce,
                    "gas": 100000,
                    "gasPrice": gas_price,
                }
            )
            signed = account.sign_transaction(tx)
            tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"  Transaction sent: {tx_hash.hex()}")
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            if receipt.status == 1:
                print("  Allowance set successfully!")
            else:
                print("  Transaction failed!")
            nonce += 1
        else:
            print("  Allowance already sufficient.\n")

    _sync_polymarket_allowance_cache(decimals, web3)


if __name__ == "__main__":
    main()
