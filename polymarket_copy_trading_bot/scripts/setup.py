"""Interactive setup wizard."""

from __future__ import annotations

import os
from pathlib import Path


def _is_valid_eth_address(address: str) -> bool:
    return address.startswith("0x") and len(address) == 42


def _is_valid_private_key(key: str) -> bool:
    key = key[2:] if key.startswith("0x") else key
    return len(key) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in key)


def _prompt(prompt: str) -> str:
    return input(prompt).strip()


def _print_header() -> None:
    print("\n" + "=" * 70)
    print("POLYMARKET COPY TRADING BOT - SETUP WIZARD")
    print("=" * 70 + "\n")
    print("This wizard will help you create your .env configuration file.")
    print("Press Ctrl+C at any time to cancel.\n")


def _print_section(title: str) -> None:
    print(f"\n--- {title} ---\n")


def _setup_user_addresses() -> str:
    _print_section("STEP 1: TRADERS TO COPY")
    print("Find top traders on:")
    print("  https://polymarket.com/leaderboard")
    print("  https://predictfolio.com\n")

    addresses = []
    while True:
        address = _prompt(f"Enter trader wallet address {len(addresses) + 1} (or Enter to finish): ")
        if not address:
            if not addresses:
                print("You must add at least one trader address.\n")
                continue
            break
        if not _is_valid_eth_address(address.lower()):
            print("Invalid Ethereum address format.\n")
            continue
        addresses.append(address.lower())
        print(f"Added: {address}\n")

    print(f"Total traders to copy: {len(addresses)}")
    return ", ".join(addresses)


def _setup_wallet() -> tuple[str, str]:
    _print_section("STEP 2: YOUR TRADING WALLET")
    print("IMPORTANT SECURITY TIPS:")
    print("  - Use a dedicated wallet for the bot")
    print("  - Never use your main wallet")
    print("  - Only keep trading capital in this wallet")
    print("  - Never share your private key\n")

    wallet = ""
    while not wallet:
        wallet = _prompt("Enter your Polygon wallet address: ")
        if not _is_valid_eth_address(wallet):
            print("Invalid wallet address format\n")
            wallet = ""

    private_key = ""
    while not private_key:
        private_key = _prompt("Enter your private key (without 0x prefix): ")
        if not _is_valid_private_key(private_key):
            print("Invalid private key format\n")
            private_key = ""
        if private_key.startswith("0x"):
            private_key = private_key[2:]

    return wallet, private_key


def _setup_database() -> str:
    _print_section("STEP 3: DATABASE")
    print("Free MongoDB Atlas: https://www.mongodb.com/cloud/atlas/register\n")
    print("Setup steps:")
    print("  1. Create free account")
    print("  2. Create a cluster")
    print("  3. Create database user")
    print("  4. Whitelist IP: 0.0.0.0/0")
    print("  5. Get connection string\n")

    mongo_uri = ""
    while not mongo_uri:
        mongo_uri = _prompt("Enter MongoDB connection string: ")
        if not mongo_uri.startswith("mongodb"):
            print("Invalid MongoDB URI.\n")
            mongo_uri = ""

    return mongo_uri


def _setup_rpc() -> str:
    _print_section("STEP 4: POLYGON RPC ENDPOINT")
    print("Get a free RPC endpoint from:")
    print("  Infura: https://infura.io")
    print("  Alchemy: https://www.alchemy.com")
    print("  Ankr: https://www.ankr.com\n")

    rpc_url = ""
    while not rpc_url:
        rpc_url = _prompt("Enter Polygon RPC URL: ")
        if not rpc_url.startswith("http"):
            print("Invalid RPC URL.\n")
            rpc_url = ""

    return rpc_url


def _setup_strategy() -> tuple[str, str, str]:
    _print_section("STEP 5: TRADING STRATEGY (OPTIONAL)")
    use_defaults = _prompt("Use default strategy settings? (Y/n): ")
    if use_defaults.lower() in {"n", "no"}:
        print("Copy Strategy Options:")
        print("  1. PERCENTAGE - Copy as % of trader position")
        print("  2. FIXED - Fixed dollar amount per trade")
        print("  3. ADAPTIVE - Adjust based on trade size\n")
        choice = _prompt("Choose strategy (1-3, default 1): ")
        strategy = "PERCENTAGE"
        if choice == "2":
            strategy = "FIXED"
        elif choice == "3":
            strategy = "ADAPTIVE"

        copy_size = _prompt("Copy size (% for PERCENTAGE, $ for FIXED, default 10.0): ") or "10.0"
        multiplier = _prompt(
            "Trade multiplier (1.0 = normal, 2.0 = aggressive, default 1.0): "
        ) or "1.0"
        return strategy, copy_size, multiplier

    print("Using default strategy: PERCENTAGE, 10%, 1.0x multiplier")
    return "PERCENTAGE", "10.0", "1.0"


def _setup_limits() -> tuple[str, str]:
    _print_section("STEP 6: RISK LIMITS (OPTIONAL)")
    use_defaults = _prompt("Use default risk limits? (Y/n): ")
    if use_defaults.lower() in {"n", "no"}:
        max_order = _prompt("Maximum order size in USD (default 100.0): ") or "100.0"
        min_order = _prompt("Minimum order size in USD (default 1.0): ") or "1.0"
        return max_order, min_order

    print("Using default limits: Max $100, Min $1")
    return "100.0", "1.0"


def _generate_env(config: dict) -> str:
    return f"""# ================================================================
# POLYMARKET COPY TRADING BOT - CONFIGURATION
# Generated by setup wizard
# ================================================================

USER_ADDRESSES='{config['USER_ADDRESSES']}'
PROXY_WALLET='{config['PROXY_WALLET']}'
PRIVATE_KEY='{config['PRIVATE_KEY']}'
MONGO_URI='{config['MONGO_URI']}'
RPC_URL='{config['RPC_URL']}'
CLOB_HTTP_URL='{config['CLOB_HTTP_URL']}'
CLOB_WS_URL='{config['CLOB_WS_URL']}'
USDC_CONTRACT_ADDRESS='{config['USDC_CONTRACT_ADDRESS']}'
COPY_STRATEGY='{config['COPY_STRATEGY']}'
COPY_SIZE='{config['COPY_SIZE']}'
TRADE_MULTIPLIER='{config['TRADE_MULTIPLIER']}'
MAX_ORDER_SIZE_USD='{config['MAX_ORDER_SIZE_USD']}'
MIN_ORDER_SIZE_USD='{config['MIN_ORDER_SIZE_USD']}'
FETCH_INTERVAL='{config.get('FETCH_INTERVAL', '1')}'
RETRY_LIMIT='{config.get('RETRY_LIMIT', '3')}'
TOO_OLD_TIMESTAMP='24'
TRADE_AGGREGATION_ENABLED='{config.get('TRADE_AGGREGATION_ENABLED', 'false')}'
TRADE_AGGREGATION_WINDOW_SECONDS='300'
REQUEST_TIMEOUT_MS='10000'
NETWORK_RETRY_LIMIT='3'
"""


def main() -> None:
    _print_header()

    user_addresses = _setup_user_addresses()
    wallet, private_key = _setup_wallet()
    mongo_uri = _setup_database()
    rpc_url = _setup_rpc()
    strategy, copy_size, multiplier = _setup_strategy()
    max_order, min_order = _setup_limits()

    config = {
        "USER_ADDRESSES": user_addresses,
        "PROXY_WALLET": wallet,
        "PRIVATE_KEY": private_key,
        "MONGO_URI": mongo_uri,
        "RPC_URL": rpc_url,
        "CLOB_HTTP_URL": "https://clob.polymarket.com/",
        "CLOB_WS_URL": "wss://ws-subscriptions-clob.polymarket.com/ws",
        "USDC_CONTRACT_ADDRESS": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "COPY_STRATEGY": strategy,
        "COPY_SIZE": copy_size,
        "TRADE_MULTIPLIER": multiplier,
        "MAX_ORDER_SIZE_USD": max_order,
        "MIN_ORDER_SIZE_USD": min_order,
    }

    env_content = _generate_env(config)
    env_path = Path(os.getcwd()) / ".env"

    if env_path.exists():
        overwrite = _prompt(".env file already exists. Overwrite? (y/N): ")
        if overwrite.lower() not in {"y", "yes"}:
            print("Setup cancelled. Your existing .env was not modified.")
            return
        backup_path = Path(os.getcwd()) / ".env.backup"
        backup_path.write_text(env_path.read_text(encoding="utf-8"), encoding="utf-8")
        print("Backed up existing .env to .env.backup")

    env_path.write_text(env_content, encoding="utf-8")

    print("\nSetup complete!")
    print(f"Configuration saved to: {env_path}")
    print("Next steps:")
    print("  1. Install dependencies: pip install -r requirements.txt")
    print("  2. Run health check: python -m polymarket_copy_trading_bot.scripts.health_check")
    print("  3. Start trading: python -m polymarket_copy_trading_bot")


if __name__ == "__main__":
    main()
