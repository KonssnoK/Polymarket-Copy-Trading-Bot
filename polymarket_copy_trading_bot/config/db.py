"""MongoDB connection helpers."""

from __future__ import annotations

from typing import Optional

from pymongo import MongoClient

from polymarket_copy_trading_bot.config.env import ENV
from polymarket_copy_trading_bot.utils.errors import DatabaseError
from polymarket_copy_trading_bot.utils.logger import Logger

_client: Optional[MongoClient] = None


def _validate_connection_string(uri: str) -> None:
    if not uri or not isinstance(uri, str):
        raise DatabaseError("MongoDB connection string is required")

    if not uri.startswith("mongodb://") and not uri.startswith("mongodb+srv://"):
        raise DatabaseError(
            "Invalid MongoDB connection string. Must start with mongodb:// or mongodb+srv://"
        )

    if uri.startswith("mongodb+srv://"):
        srv_pattern = r"^mongodb\+srv:\/\/(?:([^:]+):([^@]+)@)?([^/]+)(?:\/([^?]+))?(?:\?(.+))?$"
        if not __import__("re").match(srv_pattern, uri):
            raise DatabaseError(
                "Invalid MongoDB Atlas connection string format. Expected: "
                "mongodb+srv://username:password@cluster.mongodb.net/database"
            )


def _format_db_error(error: Exception) -> str:
    message = str(error).lower()
    code = getattr(error, "code", None)

    if code == "ENOTFOUND" or "enotfound" in message or "querysrv" in message:
        return (
            "DNS resolution failed. Check your MongoDB Atlas hostname and network."
        )
    if code == 8000 or "authentication" in message or "auth failed" in message:
        return "Authentication failed. Check username/password and URL encoding."
    if code == "ETIMEDOUT" or "timeout" in message:
        return "Connection timeout. Check IP allowlist and cluster availability."
    if code == "ECONNREFUSED" or "connection refused" in message:
        return "Connection refused. Check server status or firewall."

    return "Unknown MongoDB connection error."


def connect_db() -> MongoClient:
    global _client
    if _client is None:
        uri = ENV.mongo_uri or "mongodb://localhost:27017/polymarket_copytrading"
        _validate_connection_string(uri)

        options = {
            "serverSelectionTimeoutMS": 30000,
            "socketTimeoutMS": 45000,
            "connectTimeoutMS": 30000,
            "retryWrites": True,
            "retryReads": True,
            "maxPoolSize": 10,
            "minPoolSize": 2,
        }
        if uri.startswith("mongodb+srv://"):
            options["tls"] = True
            options["tlsAllowInvalidCertificates"] = False

        retries = 3
        last_error: Exception | None = None
        while retries > 0:
            try:
                Logger.info(f"Connecting to MongoDB... ({4 - retries}/3)")
                _client = MongoClient(uri, **options)
                _client.admin.command("ping")
                Logger.success("MongoDB connected")
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                retries -= 1
                if retries > 0:
                    delay = (4 - retries) * 2
                    Logger.warning(
                        f"Connection failed. Retrying in {delay}s ({retries} attempts left)"
                    )
                    __import__("time").sleep(delay)

        if _client is None:
            error_message = _format_db_error(last_error or Exception("Unknown"))
            Logger.error("MongoDB connection failed after all retries")
            Logger.error(f"Details: {last_error}")
            Logger.warning(error_message)
            raise DatabaseError(
                "Failed to connect to MongoDB after retries", last_error
            )
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
        raise DatabaseError("Failed to close MongoDB connection", exc)
    finally:
        _client = None
