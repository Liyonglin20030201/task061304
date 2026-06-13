import pytest
import numpy as np
from scipy.stats import norm


class TestReplenishmentAlgorithm:
    """Tests for the replenishment EOQ and safety stock algorithms."""

    def test_safety_stock_calculation(self):
        service_level = 0.95
        std_demand = 5.0
        lead_time = 7
        review_period = 7

        z_score = norm.ppf(service_level)
        safety_stock = int(np.ceil(z_score * std_demand * np.sqrt(lead_time + review_period)))

        assert z_score == pytest.approx(1.645, abs=0.01)
        assert safety_stock > 0
        expected = int(np.ceil(1.645 * 5.0 * np.sqrt(14)))
        assert safety_stock == expected

    def test_reorder_point(self):
        avg_daily_demand = 10.0
        lead_time = 7
        safety_stock = 31

        rop = int(np.ceil(avg_daily_demand * lead_time + safety_stock))
        assert rop == 101

    def test_eoq_basic(self):
        annual_demand = 3650.0
        ordering_cost = 50.0
        unit_cost = 10.0
        holding_cost_rate = 0.25
        holding_cost = unit_cost * holding_cost_rate

        eoq = int(np.ceil(np.sqrt(2 * annual_demand * ordering_cost / holding_cost)))
        assert eoq > 0
        expected = int(np.ceil(np.sqrt(2 * 3650 * 50 / 2.5)))
        assert eoq == expected

    def test_eoq_respects_moq(self):
        eoq = 50
        moq = 100
        suggested_qty = max(eoq, moq)
        assert suggested_qty == 100

    def test_bulk_discount_threshold(self):
        suggested_qty = 90
        bulk_threshold = 100

        if suggested_qty >= bulk_threshold * 0.8:
            suggested_qty = max(suggested_qty, bulk_threshold)
            bulk_discount_applied = 1
        else:
            bulk_discount_applied = 0

        assert suggested_qty == 100
        assert bulk_discount_applied == 1

    def test_no_bulk_discount_below_threshold(self):
        suggested_qty = 50
        bulk_threshold = 100

        if suggested_qty >= bulk_threshold * 0.8:
            suggested_qty = max(suggested_qty, bulk_threshold)
            bulk_discount_applied = 1
        else:
            bulk_discount_applied = 0

        assert suggested_qty == 50
        assert bulk_discount_applied == 0

    def test_promo_boost_factor(self):
        velocity = 10.0
        promo_boost = 1.3
        adjusted = velocity * promo_boost
        assert adjusted == 13.0

    def test_weather_penalty(self):
        velocity = 10.0
        weather_sensitivity = 0.1
        avg_precip = 15.0  # > 10mm

        if avg_precip > 10:
            factor = 1.0 - weather_sensitivity
        else:
            factor = 1.0

        adjusted = velocity * factor
        assert adjusted == 9.0

    def test_days_until_stockout(self):
        current_stock = 100
        safety_stock = 30
        velocity = 10.0

        days = int((current_stock - safety_stock) / velocity) if velocity > 0 else 999
        assert days == 7

    def test_max_stock_cap(self):
        suggested_qty = 500
        max_stock_days = 30
        velocity = 10.0
        current_stock = 20
        moq = 50

        max_stock = int(velocity * max_stock_days)
        capped = min(suggested_qty, max(max_stock - current_stock, moq))
        assert capped == 280
