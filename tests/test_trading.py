import unittest

from tests import context  # noqa: F401
from quant_trading.risk import RiskConfig, check_order_risk, risk_config_for_profile
from quant_trading.trading import BUY, SELL, Order, PaperBroker, build_target_order, round_down_to_lot


class TradingTests(unittest.TestCase):
    def test_paper_broker_buys_and_sells_with_costs(self):
        broker = PaperBroker(cash=10_000.0, fee_rate=0.001, slippage_rate=0.0)

        buy_fill = broker.submit_order(Order("000001", BUY, 100, 10.0, "test buy"))
        sell_fill = broker.submit_order(Order("000001", SELL, 100, 11.0, "test sell"))

        self.assertEqual(buy_fill.fee, 1.0)
        self.assertEqual(sell_fill.fee, 1.1)
        self.assertAlmostEqual(broker.cash, 10_097.9)
        self.assertEqual(broker.position_quantity("000001"), 0)

    def test_risk_rejects_order_that_breaks_cash_buffer(self):
        order = Order("000001", BUY, 1000, 10.0)

        decision = check_order_risk(
            order,
            cash=15_000.0,
            positions={},
            latest_prices={"000001": 10.0},
            config=RiskConfig(max_order_value=20_000.0, min_cash_buffer=10_000.0),
        )

        self.assertFalse(decision.approved)
        self.assertIn("cash would fall below min_cash_buffer", decision.reasons)

    def test_risk_rejects_non_lot_quantity(self):
        order = Order("000001", BUY, 101, 10.0)

        decision = check_order_risk(order, cash=100_000.0, positions={}, latest_prices={"000001": 10.0})

        self.assertFalse(decision.approved)
        self.assertIn("quantity must be a multiple of lot_size 100", decision.reasons)

    def test_build_target_order_returns_none_when_already_at_target(self):
        order = build_target_order("000001", current_quantity=100, target_quantity=100, price=10.0, reason="same")

        self.assertIsNone(order)

    def test_round_down_to_lot(self):
        self.assertEqual(round_down_to_lot(999, 100), 900)

    def test_small_2000_risk_profile(self):
        cash, config = risk_config_for_profile("small-2000")

        self.assertEqual(cash, 2_000.0)
        self.assertEqual(config.max_order_value, 1_500.0)
        self.assertEqual(config.min_cash_buffer, 300.0)


if __name__ == "__main__":
    unittest.main()
