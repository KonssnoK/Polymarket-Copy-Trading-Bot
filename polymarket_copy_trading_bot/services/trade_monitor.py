"""Trade monitoring service."""

from __future__ import annotations

import time

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.models.user_history import (
    get_user_activity_collection,
    get_user_position_collection,
)
from polymarket_copy_trading_bot.utils.error_helpers import format_error
from polymarket_copy_trading_bot.utils.fetch_data import fetch_data
from polymarket_copy_trading_bot.utils.logger import Logger
from polymarket_copy_trading_bot.utils.position_helpers import (
    calculate_position_stats,
    fetch_my_positions_and_balance,
    fetch_user_positions_and_balance,
)

USER_ADDRESSES = ENV.user_addresses
TOO_OLD_HOURS = ENV.too_old_timestamp
TOO_OLD_MINUTES = ENV.too_old_trades_minutes
FETCH_INTERVAL = ENV.fetch_interval

if not USER_ADDRESSES:
    raise RuntimeError("USER_ADDRESSES is not defined or empty")


_user_models = [
    {
        "address": address,
        "activity": get_user_activity_collection(address),
        "position": get_user_position_collection(address),
    }
    for address in USER_ADDRESSES
]


_is_first_run = True
_is_running = True


def stop_trade_monitor() -> None:
    global _is_running
    _is_running = False
    Logger.info("Trade monitor shutdown requested...")


def _format_address(address: str) -> str:
    return f"{address[:6]}...{address[-4:]}"


def _init_positions() -> None:
    counts = []
    for model in _user_models:
        count = model["activity"].count_documents({})
        counts.append(count)
    Logger.clear_line()
    Logger.db_connection(USER_ADDRESSES, counts)

    try:
        my_positions, usdc_balance, _total_balance = fetch_my_positions_and_balance()
        if my_positions:
            stats = calculate_position_stats(my_positions)
            my_top_positions = (
                sorted(my_positions, key=lambda p: float(p.get("percentPnl") or 0), reverse=True)
            )[:5]
            top_details = [
                {
                    "outcome": pos.get("outcome"),
                    "title": pos.get("title"),
                    "currentValue": pos.get("currentValue") or 0,
                    "percentPnl": pos.get("percentPnl") or 0,
                    "avgPrice": pos.get("avgPrice") or 0,
                    "curPrice": pos.get("curPrice") or 0,
                }
                for pos in my_top_positions
            ]
            Logger.clear_line()
            Logger.my_positions(
                ENV.proxy_wallet,
                len(my_positions),
                top_details,
                stats["overallPnl"],
                stats["totalValue"],
                stats["initialValue"],
                usdc_balance,
            )
        else:
            Logger.clear_line()
            Logger.my_positions(ENV.proxy_wallet, 0, [], 0, 0, 0, usdc_balance)
    except Exception as exc:  # noqa: BLE001
        Logger.error(f"Failed to fetch your positions: {format_error(exc)}")

    position_counts = []
    position_details = []
    profitabilities = []

    for model in _user_models:
        positions = list(model["position"].find({}))
        position_counts.append(len(positions))
        stats = calculate_position_stats(positions)
        profitabilities.append(stats["overallPnl"])
        top_positions = (
            sorted(positions, key=lambda p: float(p.get("percentPnl") or 0), reverse=True)
        )[:3]
        top_details = [
            {
                "outcome": pos.get("outcome"),
                "title": pos.get("title"),
                "currentValue": pos.get("currentValue") or 0,
                "percentPnl": pos.get("percentPnl") or 0,
                "avgPrice": pos.get("avgPrice") or 0,
                "curPrice": pos.get("curPrice") or 0,
            }
            for pos in top_positions
        ]
        position_details.append(top_details)

    Logger.clear_line()
    Logger.traders_positions(USER_ADDRESSES, position_counts, position_details, profitabilities)


def _get_old_trade_cutoff() -> int:
    now = int(time.time())
    if TOO_OLD_MINUTES is not None:
        return now - int(TOO_OLD_MINUTES * 60)
    return now - int(TOO_OLD_HOURS * 3600)


def _process_new_trade(activity: dict, address: str, collection, cutoff_ts: int) -> None:
    timestamp = int(activity.get("timestamp") or 0)

    transaction_hash = str(activity.get("transactionHash") or "")
    existing = collection.find_one({"transactionHash": transaction_hash})
    if existing:
        return

    too_old = timestamp < cutoff_ts
    new_activity = {
        "proxyWallet": str(activity.get("proxyWallet") or ""),
        "timestamp": timestamp,
        "conditionId": str(activity.get("conditionId") or ""),
        "type": str(activity.get("type") or ""),
        "size": float(activity.get("size") or 0),
        "usdcSize": float(activity.get("usdcSize") or 0),
        "transactionHash": transaction_hash,
        "price": float(activity.get("price") or 0),
        "asset": str(activity.get("asset") or ""),
        "side": str(activity.get("side") or ""),
        "outcomeIndex": int(activity.get("outcomeIndex") or 0),
        "title": str(activity.get("title") or ""),
        "slug": str(activity.get("slug") or ""),
        "icon": str(activity.get("icon") or ""),
        "eventSlug": str(activity.get("eventSlug") or ""),
        "outcome": str(activity.get("outcome") or ""),
        "name": str(activity.get("name") or ""),
        "pseudonym": str(activity.get("pseudonym") or ""),
        "bio": str(activity.get("bio") or ""),
        "profileImage": str(activity.get("profileImage") or ""),
        "profileImageOptimized": str(activity.get("profileImageOptimized") or ""),
        "bot": True if too_old else False,
        "botExcutedTime": 999 if too_old else 0,
    }

    collection.insert_one(new_activity)
    if not too_old:
        Logger.info(f"New trade detected for {_format_address(address)}")


def _update_trader_positions(address: str, collection) -> None:
    positions, _balance = fetch_user_positions_and_balance(address)
    for position in positions:
        collection.update_one(
            {
                "asset": position.get("asset") or "",
                "conditionId": position.get("conditionId") or "",
            },
            {"$set": position},
            upsert=True,
        )


def _fetch_trade_data() -> None:
    cutoff_ts = _get_old_trade_cutoff()
    for model in _user_models:
        address = model["address"]
        activity_collection = model["activity"]
        position_collection = model["position"]
        try:
            api_url = f"https://data-api.polymarket.com/activity?user={address}&type=TRADE"
            activities = fetch_data(api_url)
            if not isinstance(activities, list) or not activities:
                continue
            for activity in activities:
                _process_new_trade(activity, address, activity_collection, cutoff_ts)
            _update_trader_positions(address, position_collection)
        except Exception as exc:  # noqa: BLE001
            Logger.error(f"Error fetching data for {_format_address(address)}: {format_error(exc)}")


def trade_monitor() -> None:
    global _is_first_run
    _init_positions()
    Logger.success(f"Monitoring {len(USER_ADDRESSES)} trader(s) every {FETCH_INTERVAL}s")
    Logger.separator()

    if _is_first_run:
        Logger.info("First run: marking all historical trades as processed...")
        for model in _user_models:
            update_result = model["activity"].update_many(
                {"bot": False},
                {"$set": {"bot": True, "botExcutedTime": 999}},
            )
            if update_result.modified_count > 0:
                Logger.info(
                    f"Marked {update_result.modified_count} historical trades as processed for {_format_address(model['address'])}"
                )
        _is_first_run = False
        Logger.success("Historical trades processed. Now monitoring for new trades only.")
        Logger.separator()

    while _is_running:
        _fetch_trade_data()
        if not _is_running:
            break
        time.sleep(FETCH_INTERVAL)

    Logger.info("Trade monitor stopped")
