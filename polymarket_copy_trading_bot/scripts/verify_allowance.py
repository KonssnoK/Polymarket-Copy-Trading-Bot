"""Verify USDC allowance status."""

from __future__ import annotations

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV

PROXY_WALLET = ENV.proxy_wallet
RPC_URL = ENV.rpc_url
USDC_CONTRACT_ADDRESS = ENV.usdc_contract_address
POLYMARKET_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

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
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]


def main() -> None:
    print("Verifying USDC allowance status...\n")

    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    contract = web3.eth.contract(address=USDC_CONTRACT_ADDRESS, abi=USDC_ABI)

    decimals = contract.functions.decimals().call()
    balance = contract.functions.balanceOf(PROXY_WALLET).call()
    allowance = contract.functions.allowance(PROXY_WALLET, POLYMARKET_EXCHANGE).call()

    balance_formatted = Web3.from_wei(balance, "mwei")
    allowance_formatted = Web3.from_wei(allowance, "mwei")

    print("=" * 70)
    print("WALLET STATUS")
    print("=" * 70)
    print(f"Wallet:     {PROXY_WALLET}")
    print(f"USDC:       {balance_formatted} USDC")
    print(
        f"Allowance:  {'0 USDC (NOT SET!)' if allowance == 0 else str(allowance_formatted) + ' USDC (SET!)'}"
    )
    print(f"Exchange:   {POLYMARKET_EXCHANGE}")
    print("=" * 70)

    if allowance == 0:
        print("\nPROBLEM: Allowance is NOT set!")
        print("\nTO FIX: Run the following command:")
        print("   python -m polymarket_copy_trading_bot.scripts.check_allowance")
        raise SystemExit(1)
    if allowance < balance:
        print("\nWARNING: Allowance is less than your balance!")
        print(f"Balance:   {balance_formatted} USDC")
        print(f"Allowance: {allowance_formatted} USDC")
        print("\nConsider setting unlimited allowance:")
        print("   python -m polymarket_copy_trading_bot.scripts.check_allowance")
        raise SystemExit(1)

    print("\nSUCCESS: Allowance is properly set!")
    print("Start the bot:")
    print("   python -m polymarket_copy_trading_bot")


if __name__ == "__main__":
    main()