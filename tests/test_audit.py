import csv
import tempfile
import unittest
from pathlib import Path

from tests import context  # noqa: F401
from quant_trading.audit import append_audit_record, build_audit_record, write_order_review
from quant_trading.risk import RiskDecision
from quant_trading.trading import BUY, Order


class AuditTests(unittest.TestCase):
    def test_append_audit_record_writes_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.csv"
            record = build_audit_record(
                run_id="run-1",
                symbol="000001",
                trade_date="2024-01-31",
                close=10.0,
                signal=1.0,
                order=Order("000001", BUY, 100, 10.0, "test"),
                decision=RiskDecision(True, []),
                source="akshare-sina",
                cache_status="hit",
            )

            append_audit_record(path, record)

            with path.open("r", newline="", encoding="utf-8-sig") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(rows[0]["status"], "approved")
            self.assertEqual(rows[0]["quantity"], "100")

    def test_write_order_review_overwrites_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orders.csv"
            record = build_audit_record(
                run_id="run-1",
                symbol="000001",
                trade_date="2024-01-31",
                close=10.0,
                signal=0.0,
                order=None,
                decision=None,
                source="akshare-sina",
                cache_status="hit",
            )

            write_order_review(path, record)

            with path.open("r", newline="", encoding="utf-8-sig") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "no_order")


if __name__ == "__main__":
    unittest.main()
