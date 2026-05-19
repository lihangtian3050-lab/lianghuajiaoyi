from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


BUY = "buy"
SELL = "sell"
VALID_SIDES = {BUY, SELL}


@dataclass(frozen=True)
class Order:
    symbol: str
    side: str
    quantity: int
    price: float
    reason: str = ""


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: str
    quantity: int
    requested_price: float
    fill_price: float
    fee: float
    cash_delta: float
    timestamp: str
    reason: str = ""


@dataclass
class Position:
    symbol: str
    quantity: int = 0
    avg_cost: float = 0.0

    @property
    def market_value_at_cost(self) -> float:
        return self.quantity * self.avg_cost


@dataclass
class PaperBroker:
    cash: float = 100_000.0
    fee_rate: float = 0.0003
    slippage_rate: float = 0.0002
    positions: dict[str, Position] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)

    def submit_order(self, order: Order) -> Fill:
        _validate_order(order)
        if self.fee_rate < 0 or self.slippage_rate < 0:
            raise ValueError("cost rates must be non-negative")

        fill_price = _apply_slippage(order.side, order.price, self.slippage_rate)
        gross_value = fill_price * order.quantity
        fee = gross_value * self.fee_rate

        if order.side == BUY:
            total_cost = gross_value + fee
            if total_cost > self.cash:
                raise ValueError("insufficient cash")
            self.cash -= total_cost
            self._increase_position(order.symbol, order.quantity, fill_price)
            cash_delta = -total_cost
        else:
            position = self.positions.get(order.symbol, Position(order.symbol))
            if order.quantity > position.quantity:
                raise ValueError("cannot sell more than current position")
            proceeds = gross_value - fee
            self.cash += proceeds
            self._decrease_position(order.symbol, order.quantity)
            cash_delta = proceeds

        fill = Fill(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            requested_price=order.price,
            fill_price=fill_price,
            fee=fee,
            cash_delta=cash_delta,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=order.reason,
        )
        self.fills.append(fill)
        return fill

    def position_quantity(self, symbol: str) -> int:
        return self.positions.get(symbol, Position(symbol)).quantity

    def portfolio_value(self, latest_prices: dict[str, float]) -> float:
        value = self.cash
        for symbol, position in self.positions.items():
            value += position.quantity * latest_prices.get(symbol, position.avg_cost)
        return value

    def _increase_position(self, symbol: str, quantity: int, price: float) -> None:
        position = self.positions.setdefault(symbol, Position(symbol))
        total_quantity = position.quantity + quantity
        total_cost = position.avg_cost * position.quantity + price * quantity
        position.quantity = total_quantity
        position.avg_cost = total_cost / total_quantity

    def _decrease_position(self, symbol: str, quantity: int) -> None:
        position = self.positions.setdefault(symbol, Position(symbol))
        position.quantity -= quantity
        if position.quantity == 0:
            position.avg_cost = 0.0


def build_target_order(
    symbol: str,
    current_quantity: int,
    target_quantity: int,
    price: float,
    reason: str,
) -> Order | None:
    if target_quantity == current_quantity:
        return None
    side = BUY if target_quantity > current_quantity else SELL
    return Order(
        symbol=symbol,
        side=side,
        quantity=abs(target_quantity - current_quantity),
        price=price,
        reason=reason,
    )


def round_down_to_lot(quantity: int, lot_size: int = 100) -> int:
    if lot_size <= 0:
        raise ValueError("lot_size must be positive")
    if quantity <= 0:
        return 0
    return quantity - quantity % lot_size


def _validate_order(order: Order) -> None:
    if order.side not in VALID_SIDES:
        raise ValueError(f"invalid side: {order.side}")
    if order.quantity <= 0:
        raise ValueError("quantity must be positive")
    if order.price <= 0:
        raise ValueError("price must be positive")


def _apply_slippage(side: str, price: float, slippage_rate: float) -> float:
    if side == BUY:
        return price * (1 + slippage_rate)
    if side == SELL:
        return price * (1 - slippage_rate)
    raise ValueError(f"invalid side: {side}")
