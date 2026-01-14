"""USDC balance helper via Web3."""

from __future__ import annotations

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV

USDC_ABI = [
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
]


def get_my_balance(address: str) -> float:
    provider = Web3(Web3.HTTPProvider(ENV.rpc_url))
    contract = provider.eth.contract(address=ENV.usdc_contract_address, abi=USDC_ABI)
    balance = contract.functions.balanceOf(address).call()
    return float(balance) / 1_000_000