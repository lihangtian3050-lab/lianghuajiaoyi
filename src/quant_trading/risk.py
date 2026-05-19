from __future__ import annotations

from dataclasses import dataclass

from quant_trading.trading import BUY, SELL, Order, Position


@dataclass(frozen=True)
class RiskConfig:
    max_order_value: float = 20_000.0
    max_position_value: float = 30_000.0
    max_position_pct: float = 0.30
    min_cash_buffer: float = 10_000.0
    lot_size: int = 100
    allow_short: bool = False


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: list[str]


def check_order_risk(
    order: Order,
    cash: float,
    positions: dict[str, Position],
    latest_prices: dict[str, float],
    config: RiskConfig | None = None,
) -> RiskDecision:
    config = config or RiskConfig()
    reasons: list[str] = []
    if config.max_order_value <= 0 or config.max_position_value <= 0 or config.max_position_pct <= 0:
        raise ValueError("risk limits must be positive")
    if config.lot_size <= 0:
        raise ValueError("lot_size must be positive")

    order_value = order.quantity * order.price
    position = positions.get(order.symbol, Position(order.symbol))
    current_value = position.quantity * latest_prices.get(order.symbol, order.price)
    total_equity = cash + sum(pos.quantity * latest_prices.get(symbol, pos.avg_cost) for symbol, pos in positions.items())

    if order.quantity % config.lot_size != 0:
        reasons.append(f"quantity must be a multiple of lot_size {config.lot_size}")
    if order_value > config.max_order_value:
        reasons.append("order value exceeds max_order_value")

    if order.side == BUY:
        projected_cash = cash - order_value
        projected_position_value = current_value + order_value
        if projected_cash < config.min_cash_buffer:
            reasons.append("cash would fall below min_cash_buffer")
        if projected_position_value > config.max_position_value:
            reasons.append("position value exceeds max_position_value")
        if total_equity > 0 and projected_position_value / total_equity > config.max_position_pct:
            reasons.append("position value exceeds max_position_pct")
    elif order.side == SELL:
        if not config.allow_short and order.quantity > position.quantity:
            reasons.append("sell quantity exceeds current position")
    else:
        reasons.append(f"invalid side: {order.side}")

    return RiskDecision(approved=not reasons, reasons=reasons)
