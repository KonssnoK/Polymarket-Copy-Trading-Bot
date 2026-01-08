"""MongoDB connection helpers."""

from __future__ import annotations

from typing import Optional

from pymongo import MongoClient

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.logger import Logger

_client: Optional[MongoClient] = None


def connect_db() -> MongoClient:
    global _client
    if _client is None:
        uri = ENV.mongo_uri or "mongodb://localhost:27017/polymarket_copytrading"
        try:
            _client = MongoClient(uri)
            _client.admin.command("ping")
            Logger.success("MongoDB connected")
        except Exception as exc:
            Logger.error(f"MongoDB connection failed: {exc}")
            raise
    return _client


def get_db() -> MongoClient:
    if _client is None:
        return connect_db()
    return _client


def close_db() -> None:
    global _client
    if _client is None:
        return
    try:
        _client.close()
        Logger.success("MongoDB connection closed")
    except Exception as exc:
        Logger.warning(f"Error closing MongoDB connection: {exc}")
    finally:
        _client = None