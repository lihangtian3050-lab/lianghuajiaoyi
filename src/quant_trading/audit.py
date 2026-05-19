from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import csv

from quant_trading.risk import RiskDecision
from quant_trading.trading import Order


@dataclass(frozen=True)
class AuditRecord:
    run_id: str
    event_time: str
    symbol: str
    trade_date: str
    close: float
    signal: float
    action: str
    status: str
    quantity: int
    price: float
    reason: str
    risk_reasons: str
    source: str
    cache_status: str


def build_run_id(symbol: str, trade_date: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{symbol}_{trade_date}_{timestamp}"


def build_audit_record(
    run_id: str,
    symbol: str,
    trade_date: str,
    close: float,
    signal: float,
    order: Order | None,
    decision: RiskDecision | None,
    source: str,
    cache_status: str,
) -> AuditRecord:
    if order is None:
        action = "hold"
        status = "no_order"
        quantity = 0
        price = close
        reason = "target position already satisfied"
        risk_reasons = ""
    else:
        action = order.side
        status = "approved" if decision and decision.approved else "rejected"
        quantity = order.quantity
        price = order.price
        reason = order.reason
        risk_reasons = "; ".join(decision.reasons) if decision else ""

    return AuditRecord(
        run_id=run_id,
        event_time=datetime.now(timezone.utc).isoformat(),
        symbol=symbol,
        trade_date=trade_date,
        close=close,
        signal=signal,
        action=action,
        status=status,
        quantity=quantity,
        price=price,
        reason=reason,
        risk_reasons=risk_reasons,
        source=source,
        cache_status=cache_status,
    )


def append_audit_record(path: str | Path, record: AuditRecord) -> None:
    rows_path = Path(path)
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not rows_path.exists()
    with rows_path.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(record).keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(record))


def write_order_review(path: str | Path, record: AuditRecord) -> None:
    review_path = Path(path)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    with review_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(record).keys()))
        writer.writeheader()
        writer.writerow(asdict(record))
