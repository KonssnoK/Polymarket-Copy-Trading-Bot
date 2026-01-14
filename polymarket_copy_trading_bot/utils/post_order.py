"""Order execution logic for buy/sell/merge actions."""

from __future__ import annotations

from typing import Any, Dict, Optional

from polymarket_copy_trading_bot.config.copy_strategy import (
    calculate_order_size,
    get_trade_multiplier,
)
from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.interfaces.user import UserActivity, UserPosition
from polymarket_copy_trading_bot.models.user_history import get_user_activity_collection
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from polymarket_copy_trading_bot.utils.constants import DB_FIELDS, TRADING_CONSTANTS
from polymarket_copy_trading_bot.utils.error_helpers import (
    extract_order_error,
    raise_if_insufficient_funds,
)
from polymarket_copy_trading_bot.utils.errors import InsufficientFundsError
from polymarket_copy_trading_bot.utils.logger import Logger

RETRY_LIMIT = ENV.retry_limit
COPY_STRATEGY_CONFIG = ENV.copy_strategy_config

TRADE_MULTIPLIER = ENV.trade_multiplier
COPY_PERCENTAGE = ENV.copy_percentage

MIN_ORDER_SIZE_USD = TRADING_CONSTANTS.min_order_size_usd
MIN_ORDER_SIZE_TOKENS = TRADING_CONSTANTS.min_order_size_tokens


def post_order(
    clob_client: ClobClient,
    condition: str,
    my_position: Optional[UserPosition],
    user_position: Optional[UserPosition],
    trade: UserActivity,
    my_balance: float,
    user_balance: float,
    user_address: str,
) -> None:
    user_activity = get_user_activity_collection(user_address)

    if condition == "merge":
        Logger.info("Executing MERGE strategy...")
        if not my_position:
            Logger.warning("No position to merge")
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True}},
            )
            return

        remaining = float(my_position.get("size") or 0)
        if remaining < MIN_ORDER_SIZE_TOKENS:
            Logger.warning(
                f"Position size ({remaining:.2f} tokens) too small to merge - skipping"
            )
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True}},
            )
            return

        retry = 0
        abort_due_to_funds = False
        while remaining > 0 and retry < RETRY_LIMIT:
            order_book = clob_client.get_order_book(trade.get("asset", ""))
            bids = order_book.bids
            if not bids:
                Logger.warning("No bids available in order book")
                user_activity.update_one(
                    {"_id": trade.get("_id")},
                    {"$set": {DB_FIELDS.bot_executed: True}},
                )
                break

            max_bid = max(bids, key=lambda bid: float(bid.price))
            max_bid_price = float(max_bid.price)
            max_bid_size = float(max_bid.size)
            Logger.info(f"Best bid: {max_bid_size} @ ${max_bid_price}")

            max_size = max_bid_size
            price = max_bid_price
            amount = remaining if remaining <= max_size else max_size

            order_args = MarketOrderArgs(
                token_id=str(my_position.get("asset") or ""),
                amount=amount,
                price=price,
                side=SELL,
            )
            signed_order = clob_client.create_market_order(order_args)
            resp = clob_client.post_order(signed_order, OrderType.FOK)
            if resp and resp.get("success") is True:
                retry = 0
                Logger.order_result(True, f"Sold {amount} tokens at ${price}")
                remaining -= amount
            else:
                error_message = extract_order_error(resp)
                try:
                    raise_if_insufficient_funds(error_message)
                except InsufficientFundsError:
                    abort_due_to_funds = True
                    Logger.warning(
                        f"Order rejected: {error_message or 'Insufficient balance or allowance'}"
                    )
                    Logger.warning(
                        "Skipping remaining attempts. Top up funds or run check-allowance before retrying."
                    )
                    break
                retry += 1
                Logger.warning(
                    f"Order failed (attempt {retry}/{RETRY_LIMIT}){f' - {error_message}' if error_message else ''}"
                )

        if abort_due_to_funds:
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True, DB_FIELDS.bot_executed_time: RETRY_LIMIT}},
            )
            return
        if retry >= RETRY_LIMIT:
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True, DB_FIELDS.bot_executed_time: retry}},
            )
        else:
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True}},
            )
        return

    if condition == "buy":
        Logger.info("Executing BUY strategy...")
        Logger.info(f"Your balance: ${my_balance:.2f}")
        Logger.info(f"Trader bought: ${float(trade.get('usdcSize') or 0):.2f}")

        current_position_value = 0.0
        if my_position:
            current_position_value = float(my_position.get("size") or 0) * float(
                my_position.get("avgPrice") or 0
            )

        order_calc = calculate_order_size(
            COPY_STRATEGY_CONFIG,
            float(trade.get("usdcSize") or 0),
            my_balance,
            current_position_value,
        )

        Logger.info(order_calc.reasoning)
        if order_calc.final_amount == 0:
            Logger.warning(f"Cannot execute: {order_calc.reasoning}")
            if order_calc.below_minimum:
                Logger.warning("Increase COPY_SIZE or wait for larger trades")
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True}},
            )
            return

        remaining = order_calc.final_amount
        retry = 0
        abort_due_to_funds = False
        total_bought_tokens = 0.0

        token_id = str(trade.get("asset") or "")
        condition_id = str(trade.get("conditionId") or "")
        trade_price = float(trade.get("price") or 0)
        while remaining > 0 and retry < RETRY_LIMIT:
            order_book = clob_client.get_order_book(token_id)
            asks = order_book.asks
            if not asks:
                Logger.warning(
                    f"No asks available in order book (token_id={token_id}, condition_id={condition_id}, trade_price=${trade_price:.4f})"
                )
                user_activity.update_one(
                    {"_id": trade.get("_id")},
                    {"$set": {DB_FIELDS.bot_executed: True}},
                )
                break

            min_ask = min(asks, key=lambda ask: float(ask.price))
            price = float(min_ask.price)
            ask_size = float(min_ask.size)
            Logger.info(f"Best ask: {ask_size} @ ${price}")

            if price - TRADING_CONSTANTS.max_price_slippage > trade_price:
                Logger.warning("Price slippage too high - skipping trade")
                user_activity.update_one(
                    {"_id": trade.get("_id")},
                    {"$set": {DB_FIELDS.bot_executed: True}},
                )
                break

            if remaining < MIN_ORDER_SIZE_USD:
                Logger.info(
                    f"Remaining amount (${remaining:.2f}) below minimum - completing trade"
                )
                user_activity.update_one(
                    {"_id": trade.get("_id")},
                    {
                        "$set": {
                            DB_FIELDS.bot_executed: True,
                            DB_FIELDS.my_bought_size: total_bought_tokens,
                        }
                    },
                )
                break

            max_order_size = ask_size * price
            order_size = min(remaining, max_order_size)

            order_args = MarketOrderArgs(
                token_id=str(token_id),
                amount=order_size,
                price=price,
                side=BUY,
            )

            Logger.info(
                f"Creating order: ${order_size:.2f} @ ${price} (Balance: ${my_balance:.2f})"
            )
            signed_order = clob_client.create_market_order(order_args)
            resp = clob_client.post_order(signed_order, OrderType.FOK)
            if resp and resp.get("success") is True:
                retry = 0
                tokens_bought = order_size / price
                total_bought_tokens += tokens_bought
                Logger.order_result(
                    True,
                    f"Bought ${order_size:.2f} at ${price} ({tokens_bought:.2f} tokens)",
                )
                remaining -= order_size
            else:
                error_message = extract_order_error(resp)
                try:
                    raise_if_insufficient_funds(error_message)
                except InsufficientFundsError:
                    abort_due_to_funds = True
                    Logger.warning(
                        f"Order rejected: {error_message or 'Insufficient balance or allowance'}"
                    )
                    Logger.warning(
                        "Skipping remaining attempts. Top up funds or run check-allowance before retrying."
                    )
                    break
                retry += 1
                Logger.warning(
                    f"Order failed (attempt {retry}/{RETRY_LIMIT}){f' - {error_message}' if error_message else ''}"
                )

        if abort_due_to_funds:
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {
                    "$set": {
                        DB_FIELDS.bot_executed: True,
                        DB_FIELDS.bot_executed_time: RETRY_LIMIT,
                        DB_FIELDS.my_bought_size: total_bought_tokens,
                    }
                },
            )
            return
        if retry >= RETRY_LIMIT:
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {
                    "$set": {
                        DB_FIELDS.bot_executed: True,
                        DB_FIELDS.bot_executed_time: retry,
                        DB_FIELDS.my_bought_size: total_bought_tokens,
                    }
                },
            )
        else:
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True, DB_FIELDS.my_bought_size: total_bought_tokens}},
            )

        if total_bought_tokens > 0:
            Logger.info(
                f"Tracked purchase: {total_bought_tokens:.2f} tokens for future sell calculations"
            )
        return

    if condition == "sell":
        Logger.info("Executing SELL strategy...")
        remaining = 0.0

        if not my_position:
            Logger.warning("No position to sell")
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True}},
            )
            return

        previous_buys = list(
            user_activity.find(
                {
                    "asset": trade.get("asset"),
                    "conditionId": trade.get("conditionId"),
                    "side": DB_FIELDS.side_buy,
                    DB_FIELDS.bot_executed: True,
                    DB_FIELDS.my_bought_size: {"$exists": True, "$gt": 0},
                }
            )
        )

        total_bought_tokens = sum(
            float(buy.get(DB_FIELDS.my_bought_size) or 0) for buy in previous_buys
        )

        if total_bought_tokens > 0:
            Logger.info(
                f"Found {len(previous_buys)} previous purchases: {total_bought_tokens:.2f} tokens bought"
            )

        if not user_position:
            remaining = float(my_position.get("size") or 0)
            Logger.info(
                f"Trader closed entire position. Selling all your {remaining:.2f} tokens"
            )
        else:
            trade_size = float(trade.get("size") or 0)
            trader_position_before = float(user_position.get("size") or 0) + trade_size
            trader_sell_percent = trade_size / trader_position_before if trader_position_before else 0

            Logger.info(
                f"Position comparison: Trader has {trader_position_before:.2f} tokens, You have {float(my_position.get('size') or 0):.2f} tokens"
            )
            Logger.info(
                f"Trader selling: {trade_size:.2f} tokens ({trader_sell_percent * 100:.2f}% of their position)"
            )

            if total_bought_tokens > 0:
                base_sell_size = total_bought_tokens * trader_sell_percent
                Logger.info(
                    f"Calculating from tracked purchases: {total_bought_tokens:.2f} x {trader_sell_percent * 100:.2f}% = {base_sell_size:.2f} tokens"
                )
            else:
                base_sell_size = float(my_position.get("size") or 0) * trader_sell_percent
                Logger.warning(
                    f"No tracked purchases found, using current position: {float(my_position.get('size') or 0):.2f} x {trader_sell_percent * 100:.2f}% = {base_sell_size:.2f} tokens"
                )

            multiplier = get_trade_multiplier(COPY_STRATEGY_CONFIG, float(trade.get("usdcSize") or 0))
            remaining = base_sell_size * multiplier
            if multiplier != 1.0:
                Logger.info(
                    f"Applying {multiplier}x multiplier (based on trader's ${float(trade.get('usdcSize') or 0):.2f} order): {base_sell_size:.2f} -> {remaining:.2f} tokens"
                )

        if remaining < MIN_ORDER_SIZE_TOKENS:
            Logger.warning(
                f"Cannot execute: Sell amount {remaining:.2f} tokens below minimum ({MIN_ORDER_SIZE_TOKENS} token)"
            )
            Logger.warning("This happens when position sizes are too small or mismatched")
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True}},
            )
            return

        max_position = float(my_position.get("size") or 0)
        if remaining > max_position:
            Logger.warning(
                f"Calculated sell {remaining:.2f} tokens > Your position {max_position:.2f} tokens"
            )
            Logger.warning(f"Capping to maximum available: {max_position:.2f} tokens")
            remaining = max_position

        retry = 0
        abort_due_to_funds = False
        total_sold_tokens = 0.0

        token_id = str(trade.get("asset") or "")
        condition_id = str(trade.get("conditionId") or "")
        while remaining > 0 and retry < RETRY_LIMIT:
            order_book = clob_client.get_order_book(token_id)
            bids = order_book.bids
            if not bids:
                user_activity.update_one(
                    {"_id": trade.get("_id")},
                    {"$set": {DB_FIELDS.bot_executed: True}},
                )
                Logger.warning(
                    f"No bids available in order book (token_id={token_id}, condition_id={condition_id})"
                )
                break

            max_bid = max(bids, key=lambda bid: float(bid.price))
            price = float(max_bid.price)
            bid_size = float(max_bid.size)
            Logger.info(f"Best bid: {bid_size} @ ${price}")

            if remaining < MIN_ORDER_SIZE_TOKENS:
                Logger.info(
                    f"Remaining amount ({remaining:.2f} tokens) below minimum - completing trade"
                )
                user_activity.update_one(
                    {"_id": trade.get("_id")},
                    {"$set": {DB_FIELDS.bot_executed: True}},
                )
                break

            sell_amount = min(remaining, bid_size)
            if sell_amount < MIN_ORDER_SIZE_TOKENS:
                Logger.info(
                    f"Order amount ({sell_amount:.2f} tokens) below minimum - completing trade"
                )
                user_activity.update_one(
                    {"_id": trade.get("_id")},
                    {"$set": {DB_FIELDS.bot_executed: True}},
                )
                break

            order_args = MarketOrderArgs(
                token_id=str(token_id),
                amount=sell_amount,
                price=price,
                side=SELL,
            )
            signed_order = clob_client.create_market_order(order_args)
            resp = clob_client.post_order(signed_order, OrderType.FOK)
            if resp and resp.get("success") is True:
                retry = 0
                total_sold_tokens += sell_amount
                Logger.order_result(True, f"Sold {sell_amount} tokens at ${price}")
                remaining -= sell_amount
            else:
                error_message = extract_order_error(resp)
                try:
                    raise_if_insufficient_funds(error_message)
                except InsufficientFundsError:
                    abort_due_to_funds = True
                    Logger.warning(
                        f"Order rejected: {error_message or 'Insufficient balance or allowance'}"
                    )
                    Logger.warning(
                        "Skipping remaining attempts. Top up funds or run check-allowance before retrying."
                    )
                    break
                retry += 1
                Logger.warning(
                    f"Order failed (attempt {retry}/{RETRY_LIMIT}){f' - {error_message}' if error_message else ''}"
                )

        if total_sold_tokens > 0 and total_bought_tokens > 0:
            sell_percentage = total_sold_tokens / total_bought_tokens
            if sell_percentage >= 0.99:
                user_activity.update_many(
                    {
                        "asset": trade.get("asset"),
                        "conditionId": trade.get("conditionId"),
                        "side": DB_FIELDS.side_buy,
                        DB_FIELDS.bot_executed: True,
                        DB_FIELDS.my_bought_size: {"$exists": True, "$gt": 0},
                    },
                    {"$set": {DB_FIELDS.my_bought_size: 0}},
                )
                Logger.info(
                    f"Cleared purchase tracking (sold {sell_percentage * 100:.1f}% of position)"
                )
            else:
                for buy in previous_buys:
                    new_size = float(buy.get(DB_FIELDS.my_bought_size) or 0) * (1 - sell_percentage)
                    user_activity.update_one(
                        {"_id": buy.get("_id")},
                        {"$set": {DB_FIELDS.my_bought_size: new_size}},
                    )
                Logger.info(
                    f"Updated purchase tracking (sold {sell_percentage * 100:.1f}% of tracked position)"
                )

        if abort_due_to_funds:
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True, DB_FIELDS.bot_executed_time: RETRY_LIMIT}},
            )
            return
        if retry >= RETRY_LIMIT:
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True, DB_FIELDS.bot_executed_time: retry}},
            )
        else:
            user_activity.update_one(
                {"_id": trade.get("_id")},
                {"$set": {DB_FIELDS.bot_executed: True}},
            )
        return

    Logger.error(f"Unknown condition: {condition}")
