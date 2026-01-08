"""Data interfaces for user activity and positions."""

from __future__ import annotations

from typing import Optional, TypedDict


class UserActivity(TypedDict, total=False):
    _id: object
    proxyWallet: str
    timestamp: int
    conditionId: str
    type: str
    size: float
    usdcSize: float
    transactionHash: str
    price: float
    asset: str
    side: str
    outcomeIndex: int
    title: str
    slug: str
    icon: str
    eventSlug: str
    outcome: str
    name: str
    pseudonym: str
    bio: str
    profileImage: str
    profileImageOptimized: str
    bot: bool
    botExcutedTime: int
    myBoughtSize: Optional[float]


class UserPosition(TypedDict, total=False):
    _id: object
    proxyWallet: str
    asset: str
    conditionId: str
    size: float
    avgPrice: float
    initialValue: float
    currentValue: float
    cashPnl: float
    percentPnl: float
    totalBought: float
    realizedPnl: float
    percentRealizedPnl: float
    curPrice: float
    redeemable: bool
    mergeable: bool
    title: str
    slug: str
    icon: str
    eventSlug: str
    outcome: str
    outcomeIndex: int
    oppositeOutcome: str
    oppositeAsset: str
    endDate: str
    negativeRisk: bool