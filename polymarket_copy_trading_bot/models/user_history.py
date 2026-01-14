"""MongoDB collection access for user activity/position history."""

from __future__ import annotations

from pymongo.collection import Collection

from polymarket_copy_trading_bot.config.db import get_db


def _get_collection(name: str) -> Collection:
    client = get_db()
    db = client.get_default_database()
    return db[name]


def get_user_position_collection(wallet_address: str) -> Collection:
    collection_name = f"user_positions_{wallet_address}"
    return _get_collection(collection_name)


def get_user_activity_collection(wallet_address: str) -> Collection:
    collection_name = f"user_activities_{wallet_address}"
    return _get_collection(collection_name)