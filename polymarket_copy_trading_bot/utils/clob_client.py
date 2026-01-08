"""Polymarket CLOB client wrapper.

This wrapper expects py-clob-client to be installed. It mirrors the methods used
in the TypeScript implementation and provides simple enums for order types.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class OrderType(str, Enum):
    FOK = "FOK"
    GTC = "GTC"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class AssetType(str, Enum):
    COLLATERAL = "COLLATERAL"
    CONDITIONAL = "CONDITIONAL"


class SignatureType(str, Enum):
    EOA = "EOA"
    POLY_GNOSIS_SAFE = "POLY_GNOSIS_SAFE"
    POLY_PROXY = "POLY_PROXY"


@dataclass
class ApiCredentials:
    key: str
    secret: str
    passphrase: str


class ClobClientUnavailable(RuntimeError):
    pass


class ClobClient:
    def __init__(
        self,
        host: str,
        chain_id: int,
        private_key: str,
        creds: Optional[ApiCredentials] = None,
        signature_type: SignatureType = SignatureType.EOA,
        funder: Optional[str] = None,
    ) -> None:
        try:
            from py_clob_client.client import ClobClient as PyClobClient  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise ClobClientUnavailable(
                "py-clob-client is required to use the CLOB client"
            ) from exc

        self._client = PyClobClient(
            host,
            chain_id,
            private_key,
            creds,
            signature_type,
            funder,
        )

    def create_api_key(self) -> Any:
        return self._client.create_api_key()

    def derive_api_key(self) -> Any:
        return self._client.derive_api_key()

    def get_order_book(self, token_id: str) -> Any:
        return self._client.get_order_book(token_id)

    def create_market_order(self, order_args: dict) -> Any:
        return self._client.create_market_order(order_args)

    def create_order(self, order_args: dict) -> Any:
        return self._client.create_order(order_args)

    def post_order(self, signed_order: Any, order_type: OrderType) -> Any:
        return self._client.post_order(signed_order, order_type)

    def delete_api_key(self) -> Any:
        return self._client.delete_api_key()

    def get_last_trade_price(self, token_id: str) -> Any:
        return self._client.get_last_trade_price(token_id)

    def update_balance_allowance(self, params: dict) -> Any:
        return self._client.update_balance_allowance(params)

    def get_balance_allowance(self, params: dict) -> Any:
        return self._client.get_balance_allowance(params)

    def get_contract_config(self, chain_id: int) -> Any:
        return self._client.get_contract_config(chain_id)