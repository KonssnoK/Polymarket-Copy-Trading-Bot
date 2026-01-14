"""Create CLOB client with API credentials."""

from __future__ import annotations

from web3 import Web3

from py_clob_client.client import ClobClient

from polymarket_copy_trading_bot.config.env import ENV
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
    signature_type = 2 if is_proxy_safe else 0

    Logger.info(
        f"Wallet type detected: {'Gnosis Safe' if is_proxy_safe else 'EOA (Externally Owned Account)'}"
    )

    client = ClobClient(
        host,
        chain_id=chain_id,
        key=ENV.private_key,
        signature_type=signature_type,
        funder=ENV.proxy_wallet,
    )

    try:
        client.set_api_creds(client.create_or_derive_api_creds())
    except Exception as exc:  # noqa: BLE001
        extra = ""
        try:
            from py_clob_client.exceptions import PolyApiException  # type: ignore

            if isinstance(exc, PolyApiException):
                extra = f" (status={exc.status_code}, error={exc.error_msg})"
        except Exception:  # noqa: BLE001
            extra = ""
        Logger.error(f"Failed to create/derive CLOB API creds: {exc}{extra}")
        raise

    return client
