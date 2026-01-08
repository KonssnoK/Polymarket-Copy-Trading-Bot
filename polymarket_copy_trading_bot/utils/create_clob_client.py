"""Create CLOB client with API credentials."""

from __future__ import annotations

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.clob_client import ClobClient, SignatureType
from polymarket_copy_trading_bot.utils.logger import Logger


def _is_gnosis_safe(address: str) -> bool:
    try:
        provider = Web3(Web3.HTTPProvider(ENV.rpc_url))
        code = provider.eth.get_code(address)
        return code not in (b"", b"0x", b"\x00") and len(code) > 0
    except Exception as exc:  # noqa: BLE001
        Logger.error(f"Error checking wallet type: {exc}")
        return False


def create_clob_client() -> ClobClient:
    chain_id = 137
    host = ENV.clob_http_url

    is_proxy_safe = _is_gnosis_safe(ENV.proxy_wallet)
    signature_type = (
        SignatureType.POLY_GNOSIS_SAFE if is_proxy_safe else SignatureType.EOA
    )

    Logger.info(
        f"Wallet type detected: {'Gnosis Safe' if is_proxy_safe else 'EOA (Externally Owned Account)'}"
    )

    client = ClobClient(
        host,
        chain_id,
        ENV.private_key,
        None,
        signature_type,
        ENV.proxy_wallet if is_proxy_safe else None,
    )

    creds = client.create_api_key()
    if not getattr(creds, "key", None):
        creds = client.derive_api_key()

    return ClobClient(
        host,
        chain_id,
        ENV.private_key,
        creds,
        signature_type,
        ENV.proxy_wallet if is_proxy_safe else None,
    )