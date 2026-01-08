"""Set token allowance for Polymarket trading (CTF approval)."""

from __future__ import annotations

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV

PROXY_WALLET = ENV.proxy_wallet
PRIVATE_KEY = ENV.private_key
RPC_URL = ENV.rpc_url
POLYGON_CHAIN_ID = 137

POLYMARKET_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
CTF_CONTRACT = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

CTF_ABI = [
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
]


def main() -> None:
    print("Setting Token Allowance for Polymarket Trading")
    print("=" * 60)

    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    account = web3.eth.account.from_key(PRIVATE_KEY)

    contract = web3.eth.contract(address=CTF_CONTRACT, abi=CTF_ABI)

    print(f"Wallet: {PROXY_WALLET}")
    print(f"CTF Contract: {CTF_CONTRACT}")
    print(f"Polymarket Exchange: {POLYMARKET_EXCHANGE}\n")

    is_approved = contract.functions.isApprovedForAll(PROXY_WALLET, POLYMARKET_EXCHANGE).call()
    if is_approved:
        print("Tokens are already approved for trading!")
        return

    print("Tokens are NOT approved for trading")
    print("Setting approval for all tokens...\n")

    tx = contract.functions.setApprovalForAll(POLYMARKET_EXCHANGE, True).build_transaction(
        {
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address),
            "gas": 100000,
            "gasPrice": web3.eth.gas_price,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)
    print(f"Transaction sent: {tx_hash.hex()}")
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt.status == 1:
        print("Success! Tokens are now approved for trading!")
        print(f"Transaction: https://polygonscan.com/tx/{tx_hash.hex()}\n")
    else:
        print("Transaction failed!")


if __name__ == "__main__":
    main()