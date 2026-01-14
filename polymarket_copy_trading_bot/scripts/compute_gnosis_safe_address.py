"""Compute Gnosis Safe proxy using on-chain owner lookup (best effort)."""

from __future__ import annotations

from web3 import Web3

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data

PRIVATE_KEY = ENV.private_key
RPC_URL = ENV.rpc_url

GNOSIS_SAFE_PROXY_FACTORY = "0xaacfeea03eb1561c4e67d661e40682bd20e3541b"
POLYMARKET_PROXY_FACTORY = "0xab45c5a4b0c941a2f231c04c3f49182e1a254052"


def _is_safe_owner(provider: Web3, proxy_address: str, owner: str) -> bool:
    abi = [{"name": "getOwners", "outputs": [{"type": "address[]"}], "inputs": [], "stateMutability": "view", "type": "function"}]
    try:
        contract = provider.eth.contract(address=proxy_address, abi=abi)
        owners = contract.functions.getOwners().call()
        return any(o.lower() == owner.lower() for o in owners)
    except Exception:
        return False


def main() -> None:
    print("Compute Gnosis Safe proxy (best effort)\n")

    wallet = Web3().eth.account.from_key(PRIVATE_KEY)
    eoa_address = wallet.address
    print(f"EOA address: {eoa_address}\n")

    provider = Web3(Web3.HTTPProvider(RPC_URL))

    print("Checking activity for proxyWallet field...")
    try:
        activities = fetch_data(
            f"https://data-api.polymarket.com/activity?user={eoa_address}&type=TRADE"
        ) or []
        if activities:
            proxy_wallet = activities[0].get("proxyWallet")
            print(f"  proxyWallet: {proxy_wallet}\n")
            if proxy_wallet and proxy_wallet.lower() != eoa_address.lower():
                positions = fetch_data(
                    f"https://data-api.polymarket.com/positions?user={proxy_wallet}"
                ) or []
                print(f"  Proxy positions: {len(positions)}")
                if positions:
                    print("\nUpdate .env:")
                    print(f"  PROXY_WALLET={proxy_wallet}\n")
                    return
    except Exception:
        print("  Failed to fetch activity")

    print("Scanning known proxy factory logs (limited)\n")
    latest_block = provider.eth.block_number
    from_block = max(0, latest_block - 2_000_000)

    event_sig = Web3.keccak(text="ProxyCreation(address,address)").hex()
    for factory in (GNOSIS_SAFE_PROXY_FACTORY, POLYMARKET_PROXY_FACTORY):
        try:
            logs = provider.eth.get_logs(
                {
                    "fromBlock": from_block,
                    "toBlock": latest_block,
                    "address": factory,
                    "topics": [event_sig],
                }
            )
        except Exception:
            continue

        for log in logs:
            if len(log.get("topics", [])) < 2:
                continue
            proxy_address = "0x" + log["topics"][1].hex()[-40:]
            if _is_safe_owner(provider, proxy_address, eoa_address):
                print(f"Found Gnosis Safe proxy: {proxy_address}")
                print(f"Update .env with PROXY_WALLET={proxy_address}")
                return

    suspect = "0xd62531bc536bff72394fc5ef715525575787e809"
    code = provider.eth.get_code(suspect)
    is_contract = code not in (b"", b"0x")
    print(f"Suspect address {suspect} is {'contract' if is_contract else 'EOA'}")
    if is_contract and _is_safe_owner(provider, suspect, eoa_address):
        print("Suspect address appears to be your Gnosis Safe proxy.")
        print(f"Update .env with PROXY_WALLET={suspect}")


if __name__ == "__main__":
    main()