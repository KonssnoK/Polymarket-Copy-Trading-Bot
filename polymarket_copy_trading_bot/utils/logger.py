"""Console logger with simple file logging."""

from __future__ import annotations

import os
import sys
from datetime import datetime

from colorama import Fore, Style, init

init(autoreset=True)


class Logger:
    _logs_dir = os.path.join(os.getcwd(), "logs")
    _spinner_frames = ["|", "/", "-", "\\"]
    _spinner_index = 0

    @classmethod
    def _log_file(cls) -> str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        return os.path.join(cls._logs_dir, f"bot-{date_str}.log")

    @classmethod
    def _ensure_logs_dir(cls) -> None:
        if not os.path.isdir(cls._logs_dir):
            os.makedirs(cls._logs_dir, exist_ok=True)

    @classmethod
    def _write_to_file(cls, message: str) -> None:
        try:
            cls._ensure_logs_dir()
            timestamp = datetime.utcnow().isoformat()
            with open(cls._log_file(), "a", encoding="utf-8") as handle:
                handle.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

    @staticmethod
    def _format_address(address: str) -> str:
        return f"{address[:6]}...{address[-4:]}"

    @staticmethod
    def _mask_address(address: str) -> str:
        if len(address) < 10:
            return address
        return f"{address[:6]}{'*' * 34}{address[-4:]}"

    @classmethod
    def header(cls, title: str) -> None:
        line = "=" * 70
        print(Fore.CYAN + line)
        print(Fore.CYAN + Style.BRIGHT + f"  {title}")
        print(Fore.CYAN + line)
        cls._write_to_file(f"HEADER: {title}")

    @classmethod
    def info(cls, message: str) -> None:
        print(Fore.BLUE + "[INFO]", message)
        cls._write_to_file(f"INFO: {message}")

    @classmethod
    def success(cls, message: str) -> None:
        print(Fore.GREEN + "[OK]", message)
        cls._write_to_file(f"SUCCESS: {message}")

    @classmethod
    def warning(cls, message: str) -> None:
        print(Fore.YELLOW + "[WARN]", message)
        cls._write_to_file(f"WARNING: {message}")

    @classmethod
    def error(cls, message: str) -> None:
        print(Fore.RED + "[ERROR]", message)
        cls._write_to_file(f"ERROR: {message}")

    @classmethod
    def trade(cls, trader_address: str, action: str, details: dict) -> None:
        line = "-" * 70
        print(Fore.MAGENTA + line)
        print(Fore.MAGENTA + Style.BRIGHT + "  NEW TRADE DETECTED")
        print(Fore.WHITE + f"Trader: {cls._format_address(trader_address)}")
        print(Fore.WHITE + f"Action: {action}")
        if details.get("asset"):
            print(Fore.WHITE + f"Asset:  {cls._format_address(details['asset'])}")
        if details.get("side"):
            print(Fore.WHITE + f"Side:   {details['side']}")
        if details.get("amount") is not None:
            print(Fore.WHITE + f"Amount: ${details['amount']}")
        if details.get("price") is not None:
            print(Fore.WHITE + f"Price:  {details['price']}")
        if details.get("eventSlug") or details.get("slug"):
            slug = details.get("eventSlug") or details.get("slug")
            print(Fore.WHITE + f"Market: https://polymarket.com/event/{slug}")
        if details.get("transactionHash"):
            print(Fore.WHITE + f"TX:     https://polygonscan.com/tx/{details['transactionHash']}")
        print(Fore.MAGENTA + line)

        trade_log = f"TRADE: {cls._format_address(trader_address)} - {action}"
        if details.get("side"):
            trade_log += f" | Side: {details['side']}"
        if details.get("amount") is not None:
            trade_log += f" | Amount: ${details['amount']}"
        if details.get("price") is not None:
            trade_log += f" | Price: {details['price']}"
        if details.get("title"):
            trade_log += f" | Market: {details['title']}"
        if details.get("transactionHash"):
            trade_log += f" | TX: {details['transactionHash']}"
        cls._write_to_file(trade_log)

    @classmethod
    def balance(cls, my_balance: float, trader_balance: float, trader_address: str) -> None:
        print(Fore.WHITE + "Capital (USDC + Positions):")
        print(
            Fore.WHITE
            + f"  Your total capital:   ${my_balance:.2f}"
        )
        print(
            Fore.WHITE
            + f"  Trader total capital: ${trader_balance:.2f} ({cls._format_address(trader_address)})"
        )

    @classmethod
    def order_result(cls, success: bool, message: str) -> None:
        if success:
            print(Fore.GREEN + "[OK] Order executed:", message)
            cls._write_to_file(f"ORDER SUCCESS: {message}")
        else:
            print(Fore.RED + "[ERROR] Order failed:", message)
            cls._write_to_file(f"ORDER FAILED: {message}")

    @classmethod
    def startup(cls, traders: list[str], my_wallet: str) -> None:
        print("\n")
        print(Fore.CYAN + "  ____       _        ____                 ")
        print(Fore.CYAN + " |  _ \\ ___ | |_   _ / ___|___  _ __  _   _ ")
        print(Fore.CYAN + Style.BRIGHT + " | |_) / _ \\| | | | | |   / _ \\| '_ \\| | | |")
        print(Fore.MAGENTA + Style.BRIGHT + " |  __/ (_) | | |_| | |__| (_) | |_) | |_| |")
        print(Fore.MAGENTA + " |_|   \\___/|_|\\__, |\\____\\___/| .__/ \\__, |")
        print(Fore.MAGENTA + "               |___/            |_|    |___/ ")
        print(Fore.WHITE + "               Copy the best, automate success\n")

        print(Fore.CYAN + "=" * 70)
        print(Fore.CYAN + "Tracking Traders:")
        for idx, address in enumerate(traders, start=1):
            print(Fore.WHITE + f"  {idx}. {address}")
        print(Fore.CYAN + "\nYour Wallet:")
        print(Fore.WHITE + f"  {cls._mask_address(my_wallet)}\n")

    @classmethod
    def db_connection(cls, traders: list[str], counts: list[int]) -> None:
        print("\nDatabase Status:")
        for idx, address in enumerate(traders):
            count = counts[idx] if idx < len(counts) else 0
            print(Fore.WHITE + f"  {cls._format_address(address)}: {count} trades")
        print("")

    @classmethod
    def separator(cls) -> None:
        print(Fore.WHITE + "-" * 70)

    @classmethod
    def waiting(cls, trader_count: int, extra_info: str | None = None) -> None:
        timestamp = datetime.now().strftime("%I:%M:%S %p")
        spinner = cls._spinner_frames[cls._spinner_index % len(cls._spinner_frames)]
        cls._spinner_index += 1
        message = (
            f"{spinner} Waiting for trades from {trader_count} trader(s)..."
            if not extra_info
            else f"{spinner} Waiting for trades from {trader_count} trader(s)... ({extra_info})"
        )
        sys.stdout.write(Fore.WHITE + f"\r[{timestamp}] {message}  ")
        sys.stdout.flush()

    @staticmethod
    def clear_line() -> None:
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()

    @classmethod
    def my_positions(
        cls,
        wallet: str,
        count: int,
        top_positions: list[dict],
        overall_pnl: float,
        total_value: float,
        initial_value: float,
        current_balance: float,
    ) -> None:
        print("\nYOUR POSITIONS")
        print(f"  Wallet: {cls._format_address(wallet)}")
        print("")

        total_portfolio = current_balance + total_value
        print(f"  Available Cash:  ${current_balance:.2f}")
        print(f"  Total Portfolio: ${total_portfolio:.2f}")

        if count == 0:
            print("\n  No open positions")
        else:
            pnl_sign = "+" if overall_pnl >= 0 else ""
            print("")
            print(f"  Open Positions:  {count} position(s)")
            print(f"    Invested:     ${initial_value:.2f}")
            print(f"    Current Value:${total_value:.2f}")
            print(f"    Profit/Loss:  {pnl_sign}{overall_pnl:.1f}%")

            if top_positions:
                print("\n  Top Positions:")
                for pos in top_positions:
                    avg_price = pos.get("avgPrice", 0) or 0
                    cur_price = pos.get("curPrice", 0) or 0
                    print(
                        f"    - {pos.get('outcome')} - {pos.get('title', '')[:45]}"
                    )
                    pnl = pos.get("percentPnl", 0) or 0
                    pnl_sign = "+" if pnl >= 0 else ""
                    print(
                        f"      Value: ${pos.get('currentValue', 0):.2f} | PnL: {pnl_sign}{pnl:.1f}%"
                    )
                    print(
                        f"      Bought @ {(avg_price * 100):.1f}c | Current @ {(cur_price * 100):.1f}c"
                    )
        print("")

    @classmethod
    def traders_positions(
        cls,
        traders: list[str],
        position_counts: list[int],
        position_details: list[list[dict]] | None = None,
        profitabilities: list[float] | None = None,
    ) -> None:
        print("\nTRADERS YOU'RE COPYING")
        for idx, address in enumerate(traders):
            count = position_counts[idx] if idx < len(position_counts) else 0
            profit = None
            if profitabilities and idx < len(profitabilities) and count > 0:
                profit = profitabilities[idx]
            profit_str = f" | {profit:+.1f}%" if profit is not None else ""
            print(f"  {cls._format_address(address)}: {count} position(s){profit_str}")

            if position_details and idx < len(position_details):
                for pos in position_details[idx]:
                    avg_price = pos.get("avgPrice", 0) or 0
                    cur_price = pos.get("curPrice", 0) or 0
                    pnl = pos.get("percentPnl", 0) or 0
                    pnl_sign = "+" if pnl >= 0 else ""
                    print(
                        f"    - {pos.get('outcome')} - {pos.get('title', '')[:40]}"
                    )
                    print(
                        f"      Value: ${pos.get('currentValue', 0):.2f} | PnL: {pnl_sign}{pnl:.1f}%"
                    )
                    print(
                        f"      Bought @ {(avg_price * 100):.1f}c | Current @ {(cur_price * 100):.1f}c"
                    )
        print("")