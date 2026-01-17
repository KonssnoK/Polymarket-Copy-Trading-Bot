"""Trade execution service."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Dict, List

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.config.copy_strategy import CopyStrategyConfig
from polymarket_copy_trading_bot.interfaces.user import UserActivity, UserPosition
from polymarket_copy_trading_bot.models.user_history import get_user_activity_collection
from py_clob_client.client import ClobClient
from polymarket_copy_trading_bot.utils.logger import Logger
from polymarket_copy_trading_bot.utils.position_helpers import (
    fetch_my_positions_and_balance,
    fetch_user_positions_and_balance,
    find_position_by_condition_id,
)
from polymarket_copy_trading_bot.utils.post_order import post_order

TRADE_AGGREGATION_MIN_TOTAL_USD = 1.0

USER_ADDRESSES = ENV.user_addresses


@dataclass
class TradeWithUser:
    trade: UserActivity
    user_address: str


@dataclass
class AggregatedTrade:
    user_address: str
    condition_id: str
    asset: str
    side: str
    slug: str | None
    event_slug: str | None
    trades: List[TradeWithUser]
    total_usdc_size: float
    average_price: float
    first_trade_time: float
    last_trade_time: float


_trade_aggregation_buffer: Dict[str, AggregatedTrade] = {}


def _copy_strategy_for_user(user_address: str) -> CopyStrategyConfig:
    override = ENV.copy_size_by_user.get(user_address.lower())
    if override is None:
        return ENV.copy_strategy_config
    Logger.info(f"Using per-trader COPY_SIZE {override} for {user_address}")
    return replace(ENV.copy_strategy_config, copy_size=override)


def _read_temp_trades() -> List[TradeWithUser]:
    all_trades: List[TradeWithUser] = []
    for address in USER_ADDRESSES:
        collection = get_user_activity_collection(address)
        trades = list(
            collection.find(
                {
                    "$and": [
                        {"type": "TRADE"},
                        {"bot": False},
                        {"botExcutedTime": 0},
                    ]
                }
            )
        )
        for trade in trades:
            all_trades.append(TradeWithUser(trade=trade, user_address=address))
    return all_trades


def _aggregation_key(trade: TradeWithUser) -> str:
    condition_id = trade.trade.get("conditionId", "")
    asset = trade.trade.get("asset", "")
    side = trade.trade.get("side", "")
    return f"{trade.user_address}:{condition_id}:{asset}:{side}"


def _add_to_aggregation_buffer(trade: TradeWithUser) -> None:
    key = _aggregation_key(trade)
    now = time.time()
    existing = _trade_aggregation_buffer.get(key)

    usdc_size = float(trade.trade.get("usdcSize") or 0)
    price = float(trade.trade.get("price") or 0)

    if existing:
        existing.trades.append(trade)
        existing.total_usdc_size += usdc_size
        total_value = sum(
            float(item.trade.get("usdcSize") or 0)
            * float(item.trade.get("price") or 0)
            for item in existing.trades
        )
        existing.average_price = (
            total_value / existing.total_usdc_size
            if existing.total_usdc_size > 0
            else 0.0
        )
        existing.last_trade_time = now
        return

    _trade_aggregation_buffer[key] = AggregatedTrade(
        user_address=trade.user_address,
        condition_id=str(trade.trade.get("conditionId") or ""),
        asset=str(trade.trade.get("asset") or ""),
        side=str(trade.trade.get("side") or "BUY"),
        slug=trade.trade.get("slug"),
        event_slug=trade.trade.get("eventSlug"),
        trades=[trade],
        total_usdc_size=usdc_size,
        average_price=price,
        first_trade_time=now,
        last_trade_time=now,
    )


def _ready_aggregated_trades() -> List[AggregatedTrade]:
    ready: List[AggregatedTrade] = []
    now = time.time()
    window_seconds = ENV.trade_aggregation_window_seconds

    keys_to_remove: List[str] = []
    for key, agg in _trade_aggregation_buffer.items():
        time_elapsed = now - agg.first_trade_time
        if time_elapsed >= window_seconds:
            if agg.total_usdc_size >= TRADE_AGGREGATION_MIN_TOTAL_USD:
                ready.append(agg)
            else:
                Logger.info(
                    f"Trade aggregation for {agg.user_address} on {agg.slug or agg.asset}: ${agg.total_usdc_size:.2f} total from {len(agg.trades)} trades below minimum (${TRADE_AGGREGATION_MIN_TOTAL_USD}) - skipping"
                )
                for trade in agg.trades:
                    collection = get_user_activity_collection(trade.user_address)
                    collection.update_one({"_id": trade.trade.get("_id")}, {"$set": {"bot": True}})
            keys_to_remove.append(key)

    for key in keys_to_remove:
        _trade_aggregation_buffer.pop(key, None)

    return ready


def _prepare_trade_data(trade: TradeWithUser) -> dict:
    my_positions, my_usdc, my_total = fetch_my_positions_and_balance()
    user_positions, user_balance = fetch_user_positions_and_balance(trade.user_address)

    my_position = find_position_by_condition_id(my_positions, trade.trade.get("conditionId", ""))
    user_position = find_position_by_condition_id(user_positions, trade.trade.get("conditionId", ""))

    return {
        "my_position": my_position,
        "user_position": user_position,
        "my_balance": my_total,
        "user_balance": user_balance,
    }


def _execute_single_trade(clob_client: ClobClient, trade: TradeWithUser) -> None:
    collection = get_user_activity_collection(trade.user_address)
    collection.update_one({"_id": trade.trade.get("_id")}, {"$set": {"botExcutedTime": 1}})

    Logger.trade(
        trade.user_address,
        trade.trade.get("side") or "UNKNOWN",
        {
            "asset": trade.trade.get("asset"),
            "side": trade.trade.get("side"),
            "amount": trade.trade.get("usdcSize"),
            "price": trade.trade.get("price"),
            "slug": trade.trade.get("slug"),
            "eventSlug": trade.trade.get("eventSlug"),
            "transactionHash": trade.trade.get("transactionHash"),
        },
    )

    data = _prepare_trade_data(trade)
    Logger.balance(data["my_balance"], data["user_balance"], trade.user_address)
    copy_strategy_config = _copy_strategy_for_user(trade.user_address)

    condition = "buy" if trade.trade.get("side") == "BUY" else "sell"
    try:
        post_order(
            clob_client,
            condition,
            data["my_position"],
            data["user_position"],
            trade.trade,
            data["my_balance"],
            data["user_balance"],
            trade.user_address,
            copy_strategy_config,
        )
    except Exception as exc:  # noqa: BLE001
        Logger.error(f"Trade execution failed: {exc}")
        collection.update_one({"_id": trade.trade.get("_id")}, {"$set": {"bot": True}})

    Logger.separator()


def _do_trading(clob_client: ClobClient, trades: List[TradeWithUser]) -> None:
    for trade in trades:
        _execute_single_trade(clob_client, trade)


def _do_aggregated_trading(clob_client: ClobClient, aggregated_trades: List[AggregatedTrade]) -> None:
    for agg in aggregated_trades:
        Logger.header(f"AGGREGATED TRADE ({len(agg.trades)} trades combined)")
        Logger.info(f"Market: {agg.slug or agg.asset}")
        Logger.info(f"Side: {agg.side}")
        Logger.info(f"Total volume: ${agg.total_usdc_size:.2f}")
        Logger.info(f"Average price: ${agg.average_price:.4f}")

        for trade in agg.trades:
            collection = get_user_activity_collection(trade.user_address)
            collection.update_one({"_id": trade.trade.get("_id")}, {"$set": {"botExcutedTime": 1}})

        if not agg.trades:
            Logger.warning("Aggregated trade has no trades, skipping")
            continue

        data = _prepare_trade_data(agg.trades[0])
        Logger.balance(data["my_balance"], data["user_balance"], agg.user_address)
        copy_strategy_config = _copy_strategy_for_user(agg.user_address)

        first_trade = agg.trades[0].trade
        synthetic_trade = dict(first_trade)
        synthetic_trade["usdcSize"] = agg.total_usdc_size
        synthetic_trade["price"] = agg.average_price
        synthetic_trade["side"] = agg.side

        condition = "buy" if agg.side == "BUY" else "sell"
        post_order(
            clob_client,
            condition,
            data["my_position"],
            data["user_position"],
            synthetic_trade,
            data["my_balance"],
            data["user_balance"],
            agg.user_address,
            copy_strategy_config,
        )

        Logger.separator()


_is_running = True


def stop_trade_executor() -> None:
    global _is_running
    _is_running = False
    Logger.info("Trade executor shutdown requested...")


def trade_executor(clob_client: ClobClient) -> None:
    Logger.success(f"Trade executor ready for {len(USER_ADDRESSES)} trader(s)")
    if ENV.trade_aggregation_enabled:
        Logger.info(
            f"Trade aggregation enabled: {ENV.trade_aggregation_window_seconds}s window, ${TRADE_AGGREGATION_MIN_TOTAL_USD} minimum"
        )

    last_check = time.time()
    while _is_running:
        trades = _read_temp_trades()

        if ENV.trade_aggregation_enabled:
            if trades:
                Logger.clear_line()
                Logger.info(f"{len(trades)} new trade(s) detected")
                for trade in trades:
                    usdc_size = float(trade.trade.get("usdcSize") or 0)
                    if trade.trade.get("side") == "BUY" and usdc_size < TRADE_AGGREGATION_MIN_TOTAL_USD:
                        Logger.info(
                            f"Adding ${usdc_size:.2f} {trade.trade.get('side')} trade to aggregation buffer for {trade.trade.get('slug') or trade.trade.get('asset')}"
                        )
                        _add_to_aggregation_buffer(trade)
                    else:
                        Logger.clear_line()
                        Logger.header("IMMEDIATE TRADE (above threshold)")
                        _do_trading(clob_client, [trade])
                last_check = time.time()

            ready = _ready_aggregated_trades()
            if ready:
                Logger.clear_line()
                Logger.header(
                    f"{len(ready)} AGGREGATED TRADE{'S' if len(ready) > 1 else ''} READY"
                )
                _do_aggregated_trading(clob_client, ready)
                last_check = time.time()

            if not trades and not ready:
                if time.time() - last_check > 0.3:
                    buffered_count = len(_trade_aggregation_buffer)
                    if buffered_count > 0:
                        Logger.waiting(len(USER_ADDRESSES), f"{buffered_count} trade group(s) pending")
                    else:
                        Logger.waiting(len(USER_ADDRESSES))
                    last_check = time.time()
        else:
            if trades:
                Logger.clear_line()
                Logger.header(f"{len(trades)} NEW TRADE(S) TO COPY")
                _do_trading(clob_client, trades)
                last_check = time.time()
            else:
                if time.time() - last_check > 0.3:
                    Logger.waiting(len(USER_ADDRESSES))
                    last_check = time.time()

        if not _is_running:
            break
        time.sleep(0.3)

    Logger.info("Trade executor stopped")
