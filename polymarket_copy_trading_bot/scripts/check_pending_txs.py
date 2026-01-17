"""Attempt to list pending transactions and gas prices from txpool."""

from __future__ import annotations

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV

PROXY_WALLET = (ENV.proxy_wallet or "").lower()
RPC_URL = ENV.rpc_url or "https://polygon-rpc.com"


def _hex_to_int(value: str | int | None) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.startswith("0x"):
        return int(value, 16)
    return int(value)


def main() -> None:
    if not PROXY_WALLET:
        print("PROXY_WALLET is not set.")
        return

    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not web3.is_connected():
        print(f"Failed to connect to RPC: {RPC_URL}")
        return

    try:
        resp = web3.provider.make_request("txpool_content", [])
    except Exception as exc:  # noqa: BLE001
        print(f"RPC does not support txpool_content: {exc}")
        print("Try another RPC or use Polygonscan pending txs view.")
        return

    result = resp.get("result") or {}
    pending = result.get("pending") or {}
    address_pool = pending.get(PROXY_WALLET)
    if not address_pool:
        print("No pending transactions found in txpool for this address.")
        return

    print(f"Pending transactions for {PROXY_WALLET}:")
    for nonce_str, tx_list in address_pool.items():
        if not isinstance(tx_list, list):
            continue
        for tx in tx_list:
            tx_hash = tx.get("hash") or ""
            gas_price = _hex_to_int(tx.get("gasPrice"))
            to_address = tx.get("to") or ""
            print(
                f"  nonce={nonce_str} gasPrice={gas_price} to={to_address} hash={tx_hash}"
            )


if __name__ == "__main__":
    main()
