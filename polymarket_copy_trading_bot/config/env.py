"""Environment loading and validation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

from polymarket_copy_trading_bot.config.copy_strategy import (
    CopyStrategy,
    CopyStrategyConfig,
    parse_tiered_multipliers,
)
from polymarket_copy_trading_bot.utils.errors import ConfigurationError

load_dotenv()


def _is_valid_eth_address(address: str) -> bool:
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", address))


def _validate_required_env() -> None:
    required = [
        "USER_ADDRESSES",
        "PROXY_WALLET",
        "PRIVATE_KEY",
        "CLOB_HTTP_URL",
        "CLOB_WS_URL",
        "MONGO_URI",
        "RPC_URL",
        "USDC_CONTRACT_ADDRESS",
    ]

    missing = [key for key in required if not os.getenv(key)]
    if missing:
        print("\n[ERROR] Missing required environment variables")
        print(f"Missing variables: {', '.join(missing)}\n")
        print("Quick fix:")
        print("  1) Run the setup wizard: python -m polymarket_copy_trading_bot.scripts.setup")
        print("  2) Or create .env with all required variables\n")
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


def _validate_addresses() -> None:
    proxy_wallet = os.getenv("PROXY_WALLET", "")
    if proxy_wallet and not _is_valid_eth_address(proxy_wallet):
        print("\n[ERROR] Invalid wallet address\n")
        print(f"Your PROXY_WALLET: {proxy_wallet}")
        print("Expected format: 0x followed by 40 hex characters\n")
        raise ConfigurationError(f"Invalid PROXY_WALLET address format: {proxy_wallet}")

    usdc_address = os.getenv("USDC_CONTRACT_ADDRESS", "")
    if usdc_address and not _is_valid_eth_address(usdc_address):
        print("\n[ERROR] Invalid USDC contract address\n")
        print(f"Current value: {usdc_address}")
        print("Default value: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174\n")
        raise ConfigurationError(
            f"Invalid USDC_CONTRACT_ADDRESS format: {usdc_address}"
        )


def _validate_numeric_config() -> None:
    fetch_interval = int(os.getenv("FETCH_INTERVAL", "1"))
    if fetch_interval <= 0:
        raise ConfigurationError("Invalid FETCH_INTERVAL: must be a positive integer")

    retry_limit = int(os.getenv("RETRY_LIMIT", "3"))
    if retry_limit < 1 or retry_limit > 10:
        raise ConfigurationError("Invalid RETRY_LIMIT: must be between 1 and 10")

    too_old_timestamp = int(os.getenv("TOO_OLD_TIMESTAMP", "24"))
    if too_old_timestamp < 1:
        raise ConfigurationError(
            "Invalid TOO_OLD_TIMESTAMP: must be a positive integer (hours)"
        )

    request_timeout = int(os.getenv("REQUEST_TIMEOUT_MS", "10000"))
    if request_timeout < 1000:
        raise ConfigurationError("Invalid REQUEST_TIMEOUT_MS: must be at least 1000ms")

    network_retry_limit = int(os.getenv("NETWORK_RETRY_LIMIT", "3"))
    if network_retry_limit < 1 or network_retry_limit > 10:
        raise ConfigurationError("Invalid NETWORK_RETRY_LIMIT: must be between 1 and 10")


def _validate_urls() -> None:
    clob_http = os.getenv("CLOB_HTTP_URL", "")
    if clob_http and not clob_http.startswith("http"):
        raise ConfigurationError(
            f"Invalid CLOB_HTTP_URL: {clob_http}. Must be a valid HTTP/HTTPS URL."
        )

    clob_ws = os.getenv("CLOB_WS_URL", "")
    if clob_ws and not clob_ws.startswith("ws"):
        raise ConfigurationError(
            f"Invalid CLOB_WS_URL: {clob_ws}. Must be a valid WebSocket URL."
        )

    rpc_url = os.getenv("RPC_URL", "")
    if rpc_url and not rpc_url.startswith("http"):
        raise ConfigurationError(
            f"Invalid RPC_URL: {rpc_url}. Must be a valid HTTP/HTTPS URL."
        )

    mongo_uri = os.getenv("MONGO_URI", "")
    if mongo_uri and not mongo_uri.startswith("mongodb"):
        raise ConfigurationError(
            f"Invalid MONGO_URI: {mongo_uri}. Must be a valid MongoDB connection string."
        )


def _parse_user_addresses(value: str) -> list[str]:
    trimmed = value.strip()
    if trimmed.startswith("[") and trimmed.endswith("]"):
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, list):
                addresses = [str(addr).lower().strip() for addr in parsed if str(addr).strip()]
                for addr in addresses:
                    if not _is_valid_eth_address(addr):
                        raise ConfigurationError(
                            f"Invalid Ethereum address in USER_ADDRESSES: {addr}"
                        )
                return addresses
        except json.JSONDecodeError as exc:
            raise ConfigurationError(
                f"Invalid JSON format for USER_ADDRESSES: {exc}"
            ) from exc

    addresses = [addr.lower().strip() for addr in trimmed.split(",") if addr.strip()]
    for addr in addresses:
        if not _is_valid_eth_address(addr):
            raise ConfigurationError(
                f"Invalid Ethereum address in USER_ADDRESSES: {addr}"
            )
    return addresses


def _parse_copy_strategy() -> CopyStrategyConfig:
    has_legacy = os.getenv("COPY_PERCENTAGE") and not os.getenv("COPY_STRATEGY")
    if has_legacy:
        copy_percentage = float(os.getenv("COPY_PERCENTAGE", "10.0"))
        trade_multiplier = float(os.getenv("TRADE_MULTIPLIER", "1.0"))
        effective_percentage = copy_percentage * trade_multiplier

        config = CopyStrategyConfig(
            strategy=CopyStrategy.PERCENTAGE,
            copy_size=effective_percentage,
            max_order_size_usd=float(os.getenv("MAX_ORDER_SIZE_USD", "100.0")),
            min_order_size_usd=float(os.getenv("MIN_ORDER_SIZE_USD", "1.0")),
            max_position_size_usd=_optional_float("MAX_POSITION_SIZE_USD"),
            max_daily_volume_usd=_optional_float("MAX_DAILY_VOLUME_USD"),
        )

        tiers = os.getenv("TIERED_MULTIPLIERS")
        if tiers:
            config.tiered_multipliers = parse_tiered_multipliers(tiers)
        elif trade_multiplier != 1.0:
            config.trade_multiplier = trade_multiplier
        return config

    strategy_str = os.getenv("COPY_STRATEGY", "PERCENTAGE").upper()
    strategy = CopyStrategy(strategy_str) if strategy_str in CopyStrategy.__members__ else CopyStrategy.PERCENTAGE

    config = CopyStrategyConfig(
        strategy=strategy,
        copy_size=float(os.getenv("COPY_SIZE", "10.0")),
        max_order_size_usd=float(os.getenv("MAX_ORDER_SIZE_USD", "100.0")),
        min_order_size_usd=float(os.getenv("MIN_ORDER_SIZE_USD", "1.0")),
        max_position_size_usd=_optional_float("MAX_POSITION_SIZE_USD"),
        max_daily_volume_usd=_optional_float("MAX_DAILY_VOLUME_USD"),
    )

    if strategy == CopyStrategy.ADAPTIVE:
        config.adaptive_min_percent = float(
            os.getenv("ADAPTIVE_MIN_PERCENT", str(config.copy_size))
        )
        config.adaptive_max_percent = float(
            os.getenv("ADAPTIVE_MAX_PERCENT", str(config.copy_size))
        )
        config.adaptive_threshold = float(os.getenv("ADAPTIVE_THRESHOLD_USD", "500.0"))

    tiers = os.getenv("TIERED_MULTIPLIERS")
    if tiers:
        config.tiered_multipliers = parse_tiered_multipliers(tiers)
    elif os.getenv("TRADE_MULTIPLIER"):
        multiplier = float(os.getenv("TRADE_MULTIPLIER", "1.0"))
        if multiplier != 1.0:
            config.trade_multiplier = multiplier

    return config


def _optional_float(key: str) -> float | None:
    value = os.getenv(key)
    if value is None:
        return None
    return float(value)


_validate_required_env()
_validate_addresses()
_validate_numeric_config()
_validate_urls()


@dataclass(frozen=True)
class EnvConfig:
    user_addresses: list[str]
    proxy_wallet: str
    private_key: str
    clob_http_url: str
    clob_ws_url: str
    fetch_interval: int
    too_old_timestamp: int
    retry_limit: int
    trade_multiplier: float
    copy_percentage: float
    copy_strategy_config: CopyStrategyConfig
    request_timeout_ms: int
    network_retry_limit: int
    trade_aggregation_enabled: bool
    trade_aggregation_window_seconds: int
    mongo_uri: str
    rpc_url: str
    usdc_contract_address: str


ENV = EnvConfig(
    user_addresses=_parse_user_addresses(os.getenv("USER_ADDRESSES", "")),
    proxy_wallet=os.getenv("PROXY_WALLET", ""),
    private_key=os.getenv("PRIVATE_KEY", ""),
    clob_http_url=os.getenv("CLOB_HTTP_URL", ""),
    clob_ws_url=os.getenv("CLOB_WS_URL", ""),
    fetch_interval=int(os.getenv("FETCH_INTERVAL", "1")),
    too_old_timestamp=int(os.getenv("TOO_OLD_TIMESTAMP", "24")),
    retry_limit=int(os.getenv("RETRY_LIMIT", "3")),
    trade_multiplier=float(os.getenv("TRADE_MULTIPLIER", "1.0")),
    copy_percentage=float(os.getenv("COPY_PERCENTAGE", "10.0")),
    copy_strategy_config=_parse_copy_strategy(),
    request_timeout_ms=int(os.getenv("REQUEST_TIMEOUT_MS", "10000")),
    network_retry_limit=int(os.getenv("NETWORK_RETRY_LIMIT", "3")),
    trade_aggregation_enabled=os.getenv("TRADE_AGGREGATION_ENABLED", "false") == "true",
    trade_aggregation_window_seconds=int(os.getenv("TRADE_AGGREGATION_WINDOW_SECONDS", "300")),
    mongo_uri=os.getenv("MONGO_URI", ""),
    rpc_url=os.getenv("RPC_URL", ""),
    usdc_contract_address=os.getenv("USDC_CONTRACT_ADDRESS", ""),
)
