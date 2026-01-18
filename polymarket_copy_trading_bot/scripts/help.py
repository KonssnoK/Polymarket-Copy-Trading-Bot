"""Print available CLI commands."""

from __future__ import annotations


COMMANDS = [
    ("setup", "Interactive setup wizard"),
    ("health-check", "Run health checks"),
    ("check-allowance", "Check USDC balance/allowance and optionally approve"),
    ("verify-allowance", "Verify USDC allowance only"),
    ("set-token-allowance", "Approve CTF tokens for trading"),
    ("manual-sell", "Sell a position manually"),
    ("sell-large", "Sell large positions"),
    ("transfer-to-gnosis", "Transfer positions to Gnosis Safe"),
    ("fetch-history", "Fetch historical trades"),
    ("simulate", "Simulate profitability"),
    ("simulate-old", "Simulate profitability (old logic)"),
    ("sim", "Run simulations"),
    ("compare", "Compare simulation results"),
    ("check-stats", "Check your stats"),
    ("check-pnl", "Check PnL discrepancy"),
    ("check-proxy", "Check proxy wallet"),
    ("check-both", "Check both wallets"),
    ("close-stale", "Close stale positions"),
    ("close-resolved", "Close resolved positions"),
    ("redeem-resolved", "Redeem resolved positions"),
    ("get-redeemable-ids", "List redeemable positions with IDs"),
    ("redeem-by-id", "Redeem positions by ID"),
    ("check-activity", "Check recent activity"),
    ("check-pending-nonce", "Check confirmed vs pending nonce"),
    ("check-pending-txs", "List pending txs from txpool (if supported)"),
    ("find-redeem-params", "Try to derive redeem params for a token id"),
    ("check-redeem-receipt", "Inspect a redemption tx receipt for burn logs"),
    ("inspect-position", "Dump raw position payload for a token/id"),
    ("get-trade-tx", "List trade tx hashes for a position token"),
    ("find-redeem-from-tx", "Decode Conditional Tokens params from tx input"),
    ("parse-trace-ctf", "Decode CTF calls from a callTracer JSON blob"),
    ("check-erc20-balance", "Check ERC20 balance for a wallet"),
    ("unwrap-neg-risk", "Unwrap neg-risk collateral via adapter (ABI required)"),
    ("find-traders", "Find best traders"),
    ("find-low-risk", "Find low risk traders"),
    ("scan-traders", "Scan best traders"),
    ("scan-markets", "Scan traders from markets"),
    ("aggregate", "Aggregate strategy results"),
    ("audit", "Audit copy trading algorithm (fixed)"),
    ("audit-old", "Audit copy trading algorithm (legacy)"),
]


def main() -> None:
    print("Available commands:\n")
    for command, description in COMMANDS:
        print(f"  {command:<20} {description}")
    print("\nRun with: python -m polymarket_copy_trading_bot.scripts.<command>")


if __name__ == "__main__":
    main()
