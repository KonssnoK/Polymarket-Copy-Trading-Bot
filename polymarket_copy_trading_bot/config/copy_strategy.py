"""Copy trading strategy configuration and sizing logic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class CopyStrategy(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"
    ADAPTIVE = "ADAPTIVE"


@dataclass
class MultiplierTier:
    min: float
    max: Optional[float]
    multiplier: float


@dataclass
class CopyStrategyConfig:
    strategy: CopyStrategy
    copy_size: float
    adaptive_min_percent: Optional[float] = None
    adaptive_max_percent: Optional[float] = None
    adaptive_threshold: Optional[float] = None
    tiered_multipliers: Optional[List[MultiplierTier]] = None
    trade_multiplier: Optional[float] = None
    max_order_size_usd: float = 100.0
    min_order_size_usd: float = 1.0
    max_position_size_usd: Optional[float] = None
    max_daily_volume_usd: Optional[float] = None


@dataclass
class OrderSizeCalculation:
    trader_order_size: float
    base_amount: float
    final_amount: float
    strategy: CopyStrategy
    capped_by_max: bool
    reduced_by_balance: bool
    below_minimum: bool
    reasoning: str


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def _calculate_adaptive_percent(config: CopyStrategyConfig, trader_order_size: float) -> float:
    min_percent = config.adaptive_min_percent or config.copy_size
    max_percent = config.adaptive_max_percent or config.copy_size
    threshold = config.adaptive_threshold or 500.0

    if trader_order_size >= threshold:
        factor = min(1.0, trader_order_size / threshold - 1.0)
        return _lerp(config.copy_size, min_percent, factor)

    factor = trader_order_size / threshold
    return _lerp(max_percent, config.copy_size, factor)


def get_trade_multiplier(config: CopyStrategyConfig, trader_order_size: float) -> float:
    tiers = config.tiered_multipliers or []
    if tiers:
        for tier in tiers:
            if trader_order_size >= tier.min:
                if tier.max is None or trader_order_size < tier.max:
                    return tier.multiplier
        return tiers[-1].multiplier

    if config.trade_multiplier is not None:
        return config.trade_multiplier

    return 1.0


def calculate_order_size(
    config: CopyStrategyConfig,
    trader_order_size: float,
    available_balance: float,
    current_position_size: float = 0.0,
) -> OrderSizeCalculation:
    if config.strategy == CopyStrategy.PERCENTAGE:
        base_amount = trader_order_size * (config.copy_size / 100.0)
        reasoning = (
            f"{config.copy_size}% of trader's ${trader_order_size:.2f} = ${base_amount:.2f}"
        )
    elif config.strategy == CopyStrategy.FIXED:
        base_amount = config.copy_size
        reasoning = f"Fixed amount: ${base_amount:.2f}"
    elif config.strategy == CopyStrategy.ADAPTIVE:
        adaptive_percent = _calculate_adaptive_percent(config, trader_order_size)
        base_amount = trader_order_size * (adaptive_percent / 100.0)
        reasoning = (
            f"Adaptive {adaptive_percent:.1f}% of trader's ${trader_order_size:.2f} = ${base_amount:.2f}"
        )
    else:
        raise ValueError(f"Unknown strategy: {config.strategy}")

    multiplier = get_trade_multiplier(config, trader_order_size)
    final_amount = base_amount * multiplier

    if multiplier != 1.0:
        reasoning += f" x{multiplier}: ${base_amount:.2f} -> ${final_amount:.2f}"

    capped_by_max = False
    reduced_by_balance = False
    below_minimum = False

    if final_amount > config.max_order_size_usd:
        final_amount = config.max_order_size_usd
        capped_by_max = True
        reasoning += f" capped at max ${config.max_order_size_usd}"

    if config.max_position_size_usd is not None:
        new_total = current_position_size + final_amount
        if new_total > config.max_position_size_usd:
            allowed = max(0.0, config.max_position_size_usd - current_position_size)
            if allowed < config.min_order_size_usd:
                final_amount = 0.0
                reasoning += " position limit reached"
            else:
                final_amount = allowed
                reasoning += " reduced to fit position limit"

    max_affordable = available_balance * 0.99
    if final_amount > max_affordable:
        final_amount = max_affordable
        reduced_by_balance = True
        reasoning += f" reduced to fit balance (${max_affordable:.2f})"

    if final_amount < config.min_order_size_usd:
        below_minimum = True
        reasoning += f" below minimum ${config.min_order_size_usd}"
        final_amount = 0.0

    return OrderSizeCalculation(
        trader_order_size=trader_order_size,
        base_amount=base_amount,
        final_amount=final_amount,
        strategy=config.strategy,
        capped_by_max=capped_by_max,
        reduced_by_balance=reduced_by_balance,
        below_minimum=below_minimum,
        reasoning=reasoning,
    )


def validate_copy_strategy_config(config: CopyStrategyConfig) -> List[str]:
    errors: List[str] = []

    if config.copy_size <= 0:
        errors.append("copy_size must be positive")

    if config.strategy == CopyStrategy.PERCENTAGE and config.copy_size > 100:
        errors.append("copy_size for PERCENTAGE strategy should be <= 100")

    if config.max_order_size_usd <= 0:
        errors.append("max_order_size_usd must be positive")

    if config.min_order_size_usd <= 0:
        errors.append("min_order_size_usd must be positive")

    if config.min_order_size_usd > config.max_order_size_usd:
        errors.append("min_order_size_usd cannot be greater than max_order_size_usd")

    if config.strategy == CopyStrategy.ADAPTIVE:
        if config.adaptive_min_percent is None or config.adaptive_max_percent is None:
            errors.append("ADAPTIVE strategy requires adaptive_min_percent and adaptive_max_percent")
        elif config.adaptive_min_percent > config.adaptive_max_percent:
            errors.append("adaptive_min_percent cannot be greater than adaptive_max_percent")

    return errors


def get_recommended_config(balance_usd: float) -> CopyStrategyConfig:
    if balance_usd < 500:
        return CopyStrategyConfig(
            strategy=CopyStrategy.PERCENTAGE,
            copy_size=5.0,
            max_order_size_usd=20.0,
            min_order_size_usd=1.0,
            max_position_size_usd=50.0,
            max_daily_volume_usd=100.0,
        )
    if balance_usd < 2000:
        return CopyStrategyConfig(
            strategy=CopyStrategy.PERCENTAGE,
            copy_size=10.0,
            max_order_size_usd=50.0,
            min_order_size_usd=1.0,
            max_position_size_usd=200.0,
            max_daily_volume_usd=500.0,
        )
    return CopyStrategyConfig(
        strategy=CopyStrategy.ADAPTIVE,
        copy_size=10.0,
        adaptive_min_percent=5.0,
        adaptive_max_percent=15.0,
        adaptive_threshold=300.0,
        max_order_size_usd=100.0,
        min_order_size_usd=1.0,
        max_position_size_usd=1000.0,
        max_daily_volume_usd=2000.0,
    )


def parse_tiered_multipliers(tiers_str: str) -> List[MultiplierTier]:
    if not tiers_str or not tiers_str.strip():
        return []

    tiers: List[MultiplierTier] = []
    tier_defs = [t.strip() for t in tiers_str.split(",") if t.strip()]

    for tier_def in tier_defs:
        parts = tier_def.split(":")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid tier format: '{tier_def}'. Expected 'min-max:multiplier' or 'min+:multiplier'"
            )

        range_part, multiplier_str = parts
        multiplier = float(multiplier_str)
        if multiplier < 0:
            raise ValueError(
                f"Invalid multiplier in tier '{tier_def}': {multiplier_str}"
            )

        if range_part.endswith("+"):
            min_val = float(range_part[:-1])
            if min_val < 0:
                raise ValueError(f"Invalid minimum value in tier '{tier_def}'")
            tiers.append(MultiplierTier(min=min_val, max=None, multiplier=multiplier))
        elif "-" in range_part:
            min_str, max_str = range_part.split("-", 1)
            min_val = float(min_str)
            max_val = float(max_str)
            if min_val < 0 or max_val <= min_val:
                raise ValueError(
                    f"Invalid range in tier '{tier_def}': {min_val}-{max_val}"
                )
            tiers.append(MultiplierTier(min=min_val, max=max_val, multiplier=multiplier))
        else:
            raise ValueError(
                f"Invalid range format in tier '{tier_def}'. Use 'min-max' or 'min+'"
            )

    tiers.sort(key=lambda tier: tier.min)

    for idx in range(len(tiers) - 1):
        current = tiers[idx]
        next_tier = tiers[idx + 1]
        if current.max is None:
            raise ValueError(
                f"Tier with infinite upper bound must be last: {current.min}+"
            )
        if current.max > next_tier.min:
            raise ValueError(
                f"Overlapping tiers: [{current.min}-{current.max}] and [{next_tier.min}-{next_tier.max}]"
            )

    return tiers