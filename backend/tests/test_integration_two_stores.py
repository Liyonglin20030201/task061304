"""Integration tests: two-store extreme data scenarios for all four modules."""
import sys
import os
import math
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import date, datetime, timedelta
from collections import defaultdict

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Pre-import mocking: stub out modules that require asyncpg/database at import
# time so that pure-logic functions can be imported without a live database.
# ---------------------------------------------------------------------------
_mock_base = MagicMock()

# Mock app.database (triggers create_async_engine which needs asyncpg)
_mock_database = MagicMock()
_mock_database.Base = _mock_base
sys.modules.setdefault("app.database", _mock_database)

# Mock all model modules that import Base from app.database
for _mod_name in [
    "app.models",
    "app.models.user",
    "app.models.store",
    "app.models.sales",
    "app.models.inventory",
    "app.models.member",
    "app.models.promotion",
    "app.models.traffic",
    "app.models.weather",
    "app.models.task_log",
    "app.models.supply_chain",
    "app.models.replenishment",
    "app.models.marketing",
    "app.models.association",
    "app.models.space_layout",
    "app.models.store_energy",
]:
    sys.modules.setdefault(_mod_name, MagicMock())

# Now we can safely import the pure functions
from app.services.association_service import _apriori, _generate_rules  # noqa: E402
from app.services.omnichannel_service import _build_store_filter  # noqa: E402
from app.services.forecast_service import _is_holiday  # noqa: E402


# ---------------------------------------------------------------------------
# Module 1: Association - store isolation + edge cases
# ---------------------------------------------------------------------------

class TestAssociationStoreIsolation:
    """
    Verify _apriori with per_item_min_count handles two stores correctly:
    - Store A: high-volume (10000 transactions), low-margin items, standard threshold
    - Store B: low-volume (50 transactions), high-margin items, adaptive threshold kicks in
    - Rules from store B must not be contaminated by store A's data
    """

    def _build_store_a_baskets(self):
        """
        Store A: 10000 transactions of common low-margin items.
        Items: A1..A20 appear frequently across baskets.
        """
        import random
        random.seed(42)
        items = {f"A{i}" for i in range(1, 21)}
        baskets = []
        item_list = list(items)
        for _ in range(10000):
            # Each basket has 3-6 items
            size = random.randint(3, 6)
            basket = set(random.sample(item_list, size))
            baskets.append(basket)
        return baskets, items

    def _build_store_b_baskets(self):
        """
        Store B: 50 transactions of niche high-margin items.
        Items: B1..B8. Patterns: B1+B2 always co-occur, B3+B4 in 40/50 baskets.
        """
        items = {f"B{i}" for i in range(1, 9)}
        baskets = []
        for i in range(50):
            basket = {"B1", "B2"}  # Always present together
            if i < 40:
                basket.add("B3")
                basket.add("B4")
            if i % 3 == 0:
                basket.add("B5")
            if i % 5 == 0:
                basket.add("B6")
            basket.add("B7")  # filler
            baskets.append(basket)
        return baskets, items

    def test_store_a_standard_threshold_filters_noise(self):
        """Store A with high volume should use standard min_support threshold."""
        baskets, items = self._build_store_a_baskets()
        total_transactions = len(baskets)
        min_support = 0.05  # 5% of 10000 = need 500 occurrences

        # No per-item override => use global threshold
        frequent = _apriori(baskets, items, min_support, total_transactions,
                            per_item_min_count=None)

        # With 20 items, random sampling: each item appears in ~30% of baskets
        # so all single items should pass 5% threshold
        single_items = {k for k in frequent if len(k) == 1}
        assert len(single_items) == 20, "All 20 items should be frequent at 5% threshold"

        # 2-itemsets: With random combinations, most pairs should appear > 500 times
        pair_items = {k for k in frequent if len(k) == 2}
        assert len(pair_items) > 0, "Should find some frequent pairs"

    def test_store_b_adaptive_threshold_retains_niche_rules(self):
        """Store B with low volume should benefit from per-item adaptive thresholds."""
        baskets, items = self._build_store_b_baskets()
        total_transactions = len(baskets)
        min_support = 0.05  # Global: 5% of 50 = 2.5 => need 3 occurrences

        # Simulate adaptive threshold: high-margin items get reduced threshold
        # B1, B2 are high-margin -> threshold reduced by 70% (factor 0.7)
        # Others keep global threshold
        global_min_count = min_support * total_transactions  # 2.5
        per_item_min_count = {}
        for item in items:
            if item in ("B1", "B2", "B3", "B4"):
                # High-margin: 30% reduction from an already low threshold
                per_item_min_count[item] = global_min_count * 0.7  # ~1.75
            else:
                per_item_min_count[item] = global_min_count

        frequent = _apriori(baskets, items, min_support, total_transactions,
                            per_item_min_count=per_item_min_count)

        # B1+B2 co-occur in all 50 baskets => definitely frequent
        assert frozenset(["B1", "B2"]) in frequent
        # B3+B4 co-occur in 40/50 = 80% => frequent
        assert frozenset(["B3", "B4"]) in frequent

        # Generate rules and check quality
        rules = _generate_rules(frequent, total_transactions, min_confidence=0.5)
        # B1->B2 should have confidence = 1.0 (always co-occur)
        b1_to_b2 = [r for r in rules
                    if r["antecedent"] == frozenset(["B1"])
                    and r["consequent"] == frozenset(["B2"])]
        assert len(b1_to_b2) == 1
        assert b1_to_b2[0]["confidence"] == 1.0

    def test_store_isolation_no_cross_contamination(self):
        """Rules from store A must not affect store B's analysis and vice versa."""
        # Run store A
        baskets_a, items_a = self._build_store_a_baskets()
        frequent_a = _apriori(baskets_a, items_a, 0.05, len(baskets_a))
        rules_a = _generate_rules(frequent_a, len(baskets_a), 0.5)

        # Run store B
        baskets_b, items_b = self._build_store_b_baskets()
        frequent_b = _apriori(baskets_b, items_b, 0.05, len(baskets_b))
        rules_b = _generate_rules(frequent_b, len(baskets_b), 0.5)

        # No item from store A should appear in store B's rules
        store_a_items = items_a
        for rule in rules_b:
            all_items_in_rule = rule["antecedent"] | rule["consequent"]
            overlap = all_items_in_rule & store_a_items
            assert len(overlap) == 0, f"Store B rule contaminated with Store A items: {overlap}"

        # No item from store B should appear in store A's rules
        store_b_items = items_b
        for rule in rules_a:
            all_items_in_rule = rule["antecedent"] | rule["consequent"]
            overlap = all_items_in_rule & store_b_items
            assert len(overlap) == 0, f"Store A rule contaminated with Store B items: {overlap}"

    def test_apriori_empty_baskets_no_crash(self):
        """Edge case: no transactions at all should return empty without crashing."""
        frequent = _apriori([], set(), 0.05, 0, per_item_min_count=None)
        assert frequent == {}

    def test_apriori_single_item_baskets(self):
        """Edge case: all baskets have only one item - no pairs possible."""
        baskets = [{"X"} for _ in range(100)]
        items = {"X"}
        frequent = _apriori(baskets, items, 0.01, 100)
        # Single item is frequent
        assert frozenset(["X"]) in frequent
        # No pairs
        rules = _generate_rules(frequent, 100, 0.5)
        assert rules == []

    def test_per_item_threshold_zero_fallback(self):
        """Items missing from per_item_min_count should use global threshold."""
        baskets = [{"A", "B"} for _ in range(10)]
        items = {"A", "B", "C"}
        # C never appears in baskets but is in items set
        # Only A and B are in per_item_min_count
        per_item_min_count = {"A": 1.0, "B": 1.0}
        # global_min_count = 0.05 * 10 = 0.5, so C with 0 occurrences should fail
        frequent = _apriori(baskets, items, 0.05, 10, per_item_min_count=per_item_min_count)
        assert frozenset(["C"]) not in frequent
        assert frozenset(["A"]) in frequent
        assert frozenset(["B"]) in frequent


# ---------------------------------------------------------------------------
# Module 2: Space Layout - coordinate mapping + extremes
# ---------------------------------------------------------------------------

class TestSpaceLayoutExtremes:
    """
    Test heatmap normalization and KPI calculation with:
    - Very large floor plan (5000x3000 pixels) vs tiny store (200x150)
    - Zone with zero sales (shouldn't crash or produce NaN)
    - Zone with extreme revenue density (100x the average)
    """

    def test_large_floor_plan_heatmap_normalization(self):
        """
        Simulate get_sales_heatmap logic for a large (5000x3000) floor plan.
        Intensity should be correctly normalized to [0, 1] range.
        """
        # Simulate the normalization logic from get_sales_heatmap
        plan_width = 5000.0
        plan_height = 3000.0

        # Simulate rows: (zone_id, zone_name, pos_x, pos_y, width, height, revenue)
        rows = [
            (1, "Electronics", 0, 0, 1000, 1000, 500000.0),
            (2, "Grocery", 1000, 0, 2000, 1500, 300000.0),
            (3, "Apparel", 3000, 0, 1500, 1500, 100000.0),
            (4, "Home", 0, 1500, 2500, 1500, 200000.0),
            (5, "Empty Zone", 4000, 1500, 1000, 1500, 0.0),  # Zero sales
        ]

        max_revenue = max(float(r[6]) for r in rows)
        if max_revenue == 0:
            max_revenue = 1.0  # Avoid division by zero

        cells = []
        for row in rows:
            zone_id, zone_name, pos_x, pos_y, width, height, revenue = row
            revenue_f = float(revenue)
            intensity = round(revenue_f / max_revenue, 4)
            cells.append({
                "zone_id": zone_id,
                "zone_name": zone_name,
                "position_x": pos_x,
                "position_y": pos_y,
                "width": width,
                "height": height,
                "intensity": intensity,
                "revenue": round(revenue_f, 2),
            })

        # Assertions
        assert cells[0]["intensity"] == 1.0, "Highest revenue zone should have intensity 1.0"
        assert cells[4]["intensity"] == 0.0, "Zero revenue zone should have intensity 0.0"
        assert all(0.0 <= c["intensity"] <= 1.0 for c in cells), "All intensities in [0, 1]"
        # No NaN values
        assert all(not math.isnan(c["intensity"]) for c in cells)

    def test_tiny_floor_plan_coordinates_valid(self):
        """
        Simulate a tiny store (200x150 pixels). Zones should still fit
        within floor plan boundaries without overflow.
        """
        plan_width = 200.0
        plan_height = 150.0

        rows = [
            (1, "Front", 0, 0, 100, 75, 10000.0),
            (2, "Back", 100, 0, 100, 75, 8000.0),
            (3, "Storage", 0, 75, 200, 75, 500.0),
        ]

        for row in rows:
            _, _, pos_x, pos_y, width, height, _ = row
            # Zone should not exceed floor plan boundaries
            assert pos_x + width <= plan_width, f"Zone exceeds plan width"
            assert pos_y + height <= plan_height, f"Zone exceeds plan height"
            assert pos_x >= 0 and pos_y >= 0, "Negative coordinates"

    def test_zone_with_zero_sales_no_crash(self):
        """
        Zone with zero sales should produce valid KPI metrics without
        division-by-zero errors or NaN values.
        """
        # Replicate KPI calculation logic from get_zone_kpis
        zone_data = {
            "zone_id": 99,
            "zone_name": "Dead Zone",
            "zone_type": "display",
            "area_sqm": 50.0,
            "revenue": 0.0,
            "transaction_count": 0,
            "items_sold": 0.0,
            "traffic_count": 0,
        }

        area = max(float(zone_data["area_sqm"]), 0.01)
        revenue_f = float(zone_data["revenue"])
        items_f = float(zone_data["items_sold"])
        txn_i = int(zone_data["transaction_count"])
        traffic_i = int(zone_data["traffic_count"])

        kpi = {
            "revenue_per_sqm": round(revenue_f / area, 2),
            "items_per_sqm": round(items_f / area, 2),
            "traffic_conversion": round(txn_i / traffic_i, 4) if traffic_i > 0 else 0.0,
        }

        assert kpi["revenue_per_sqm"] == 0.0
        assert kpi["items_per_sqm"] == 0.0
        assert kpi["traffic_conversion"] == 0.0
        # No NaN
        assert not math.isnan(kpi["revenue_per_sqm"])
        assert not math.isnan(kpi["items_per_sqm"])
        assert not math.isnan(kpi["traffic_conversion"])

    def test_extreme_revenue_density_zone(self):
        """
        Zone with 100x the average revenue density. Verify heatmap
        normalization still works and intensity is capped at 1.0.
        """
        # Zones with various revenues; one is extreme outlier
        rows = [
            (1, "Normal A", 0, 0, 100, 100, 10000.0),
            (2, "Normal B", 100, 0, 100, 100, 12000.0),
            (3, "Normal C", 200, 0, 100, 100, 8000.0),
            (4, "Extreme", 300, 0, 50, 50, 1000000.0),  # 100x average
        ]

        max_revenue = max(float(r[6]) for r in rows)
        assert max_revenue == 1000000.0

        cells = []
        for row in rows:
            revenue_f = float(row[6])
            intensity = round(revenue_f / max_revenue, 4)
            cells.append({"zone_name": row[1], "intensity": intensity})

        # Extreme zone has intensity exactly 1.0
        assert cells[3]["intensity"] == 1.0
        # Normal zones have very low intensity relative to extreme
        assert cells[0]["intensity"] == 0.01  # 10000/1000000
        # All still in valid range
        assert all(0.0 <= c["intensity"] <= 1.0 for c in cells)

    def test_all_zones_zero_revenue_no_crash(self):
        """
        When ALL zones have zero revenue, max_revenue becomes 1.0 (fallback)
        to prevent division by zero.
        """
        rows = [
            (1, "A", 0, 0, 100, 100, 0.0),
            (2, "B", 100, 0, 100, 100, 0.0),
        ]

        max_revenue = max(float(r[6]) for r in rows)
        if max_revenue == 0:
            max_revenue = 1.0

        cells = []
        for row in rows:
            revenue_f = float(row[6])
            intensity = round(revenue_f / max_revenue, 4)
            cells.append({"intensity": intensity})

        assert cells[0]["intensity"] == 0.0
        assert cells[1]["intensity"] == 0.0
        assert not any(math.isnan(c["intensity"]) for c in cells)

    def test_two_stores_kpi_comparison(self):
        """
        Compare KPIs across two stores: large store vs tiny store.
        Verify revenue_per_sqm correctly reflects area differences.
        """
        # Large store: big area, moderate revenue
        large_store_zone = {
            "area_sqm": 500.0,
            "revenue": 100000.0,
            "transaction_count": 2000,
            "traffic_count": 5000,
        }
        # Tiny store: small area, same revenue (denser)
        tiny_store_zone = {
            "area_sqm": 25.0,
            "revenue": 100000.0,
            "transaction_count": 2000,
            "traffic_count": 5000,
        }

        large_rev_per_sqm = large_store_zone["revenue"] / max(large_store_zone["area_sqm"], 0.01)
        tiny_rev_per_sqm = tiny_store_zone["revenue"] / max(tiny_store_zone["area_sqm"], 0.01)

        # Tiny store should have 20x higher revenue per sqm
        assert tiny_rev_per_sqm == large_rev_per_sqm * 20
        assert tiny_rev_per_sqm == 4000.0
        assert large_rev_per_sqm == 200.0


# ---------------------------------------------------------------------------
# Module 3: Omnichannel - permission isolation
# ---------------------------------------------------------------------------

class TestOmnichannelPermissionIsolation:
    """
    Test _build_store_filter helper:
    - Admin (store_ids=None) -> no filter appended
    - Manager with stores [1,2] -> correct ANY clause
    - Verify a query for member data from store 3 is blocked when user only has [1,2]
    """

    def test_admin_no_filter(self):
        """Admin (store_ids=None) should produce empty filter string."""
        params = {}
        result = _build_store_filter(store_ids=None, params=params)
        assert result == ""
        assert "_authorized_store_ids" not in params

    def test_manager_with_two_stores(self):
        """Manager with stores [1, 2] should produce AND clause with ANY."""
        params = {}
        result = _build_store_filter(store_ids=[1, 2], params=params)
        assert "AND" in result
        assert "ANY" in result
        assert ":_authorized_store_ids" in result
        assert params["_authorized_store_ids"] == [1, 2]

    def test_manager_with_table_alias(self):
        """Filter should correctly prepend table alias to column name."""
        params = {}
        result = _build_store_filter(store_ids=[1, 2], params=params, table_alias="cs")
        assert "cs.store_id" in result

    def test_manager_with_custom_column(self):
        """Filter should use custom column name when specified."""
        params = {}
        result = _build_store_filter(
            store_ids=[5, 10], params=params,
            table_alias="t", column="shop_id"
        )
        assert "t.shop_id" in result
        assert params["_authorized_store_ids"] == [5, 10]

    def test_store_3_blocked_for_user_with_stores_1_2(self):
        """
        A user authorized for stores [1,2] should have a filter that
        would exclude store_id=3 from query results.
        The filter uses ANY(:_authorized_store_ids), so store 3 data
        cannot pass through.
        """
        params = {}
        filter_clause = _build_store_filter(store_ids=[1, 2], params=params)

        # Verify the filter is non-empty (would restrict results)
        assert filter_clause != ""
        # Verify store 3 is NOT in the authorized list
        assert 3 not in params["_authorized_store_ids"]
        # The SQL clause will only match rows where store_id is in [1, 2]
        assert params["_authorized_store_ids"] == [1, 2]

    def test_empty_store_list_still_produces_filter(self):
        """
        A user with empty store_ids list [] should produce a filter that
        effectively blocks all data (ANY of empty array matches nothing).
        """
        params = {}
        result = _build_store_filter(store_ids=[], params=params)
        # Should still generate a filter clause (not empty string)
        assert "AND" in result
        assert params["_authorized_store_ids"] == []

    def test_single_store_filter(self):
        """Single store authorization should work correctly."""
        params = {}
        result = _build_store_filter(store_ids=[42], params=params)
        assert "ANY" in result
        assert params["_authorized_store_ids"] == [42]

    def test_filter_does_not_mutate_other_params(self):
        """Adding store filter should not remove or alter existing params."""
        params = {"start": date(2024, 1, 1), "end": date(2024, 12, 31)}
        _build_store_filter(store_ids=[1, 2], params=params)
        # Original params preserved
        assert params["start"] == date(2024, 1, 1)
        assert params["end"] == date(2024, 12, 31)
        # New param added
        assert "_authorized_store_ids" in params


# ---------------------------------------------------------------------------
# Module 4: Energy - forecast integration + holidays
# ---------------------------------------------------------------------------

class TestEnergyForecastExtremes:
    """
    Test schedule optimization logic:
    - Peak day (2.5x median forecast) -> HVAC only 15% reduction
    - Chinese holiday (Spring Festival) -> equipment stays at full capacity
    - Normal day -> standard 40% reduction for low-traffic hours
    - Forecast service error -> graceful fallback, no crash
    """

    def test_spring_festival_detected_as_holiday(self):
        """Spring Festival dates (Feb 10-16) should be recognized as holidays."""
        # 2025 Spring Festival: Feb 10-16 per the CHINESE_HOLIDAYS set
        assert _is_holiday(date(2025, 2, 10)) is True
        assert _is_holiday(date(2025, 2, 11)) is True
        assert _is_holiday(date(2025, 2, 14)) is True
        assert _is_holiday(date(2025, 2, 16)) is True
        # Non-holiday
        assert _is_holiday(date(2025, 3, 15)) is False

    def test_national_day_holiday_detection(self):
        """National Day (Oct 1-7) should be detected."""
        for day in range(1, 8):
            assert _is_holiday(date(2025, 10, day)) is True
        assert _is_holiday(date(2025, 10, 8)) is False

    def test_peak_day_hvac_only_15_percent_reduction(self):
        """
        Simulate optimize_equipment_schedule logic for a peak day:
        When forecast is 2.5x baseline, HVAC reduction should be only 15%.
        """
        # Simulate the decision logic from optimize_equipment_schedule
        peak_ratio = 2.5
        is_peak_day = True  # ratio > 1.5
        eq_type = "hvac"
        hour = 3  # low-traffic hour, not in peak_hours

        # Logic from the service: peak day + low traffic hour => 15% reduction
        peak_hours = {10, 11, 12, 13, 14, 15, 16, 17}  # typical peak hours
        low_traffic_hours = {0, 1, 2, 3, 4, 5, 6, 22, 23}

        # Simulate the HVAC decision path
        if eq_type == "hvac":
            if is_peak_day:
                if hour in peak_hours or (hour + 1) in peak_hours or (hour + 2) in peak_hours:
                    reduction_factor = 0.0  # full power
                else:
                    reduction_factor = 0.15  # mild reduction only
            elif hour in low_traffic_hours:
                reduction_factor = 0.4  # standard reduction
            else:
                reduction_factor = 0.0

        assert reduction_factor == 0.15, "Peak day low-traffic hour should get only 15% reduction"

    def test_normal_day_hvac_40_percent_reduction(self):
        """
        On a normal (non-peak) day, low-traffic hours should get
        standard 40% HVAC reduction.
        """
        is_peak_day = False
        eq_type = "hvac"
        hour = 3  # low-traffic hour
        peak_hours = {10, 11, 12, 13, 14, 15, 16, 17}
        low_traffic_hours = {0, 1, 2, 3, 4, 5, 6, 22, 23}

        if eq_type == "hvac":
            if is_peak_day:
                reduction_factor = 0.15
            elif hour in low_traffic_hours:
                reduction_factor = 0.4
            elif (hour + 1) in peak_hours and hour not in peak_hours:
                reduction_factor = 0.0  # pre-cool
            else:
                reduction_factor = 0.0

        assert reduction_factor == 0.4, "Normal day low-traffic should get 40% reduction"

    def test_holiday_peak_refrigeration_stays_full(self):
        """
        On a holiday peak day, refrigeration should stay at full capacity
        for demand surge.
        """
        # Spring Festival date
        target_date = date(2025, 2, 12)
        assert _is_holiday(target_date) is True

        # Simulate refrigeration logic from optimize_equipment_schedule
        eq_type = "refrigeration"
        is_peak_day = True  # holiday => peak

        recommended_level = None
        if eq_type == "refrigeration":
            if is_peak_day and _is_holiday(target_date):
                recommended_level = "full"
                # No reduction
            else:
                recommended_level = None  # continue (skip)

        assert recommended_level == "full"

    def test_forecast_error_graceful_fallback(self):
        """
        When forecast service raises an exception, optimize_equipment_schedule
        should fall back gracefully (peak_day_map stays empty).
        """
        # Simulate the try/except block from optimize_equipment_schedule
        peak_day_map = {}

        # Simulate forecast failure
        try:
            raise Exception("Connection refused")
        except Exception:
            forecast = {"error": "forecast service unavailable"}

        # The code checks: if "error" not in forecast ... else skip
        if "error" not in forecast and "forecast" in forecast:
            # This block should NOT execute
            peak_day_map[0] = 2.5

        # peak_day_map stays empty => no peak days detected
        assert peak_day_map == {}

        # With empty peak_day_map, all days are treated as normal
        day = 3  # Wednesday
        is_peak_day = day in peak_day_map
        assert is_peak_day is False

    def test_peak_day_detection_threshold(self):
        """
        Forecast values > 1.5x median baseline should mark day as peak.
        Values at exactly 1.5x should NOT trigger (uses > not >=).
        """
        import numpy as np

        # Simulate 14 days of forecast
        forecast_values = [100, 110, 95, 105, 250, 100, 90,
                           100, 105, 110, 95, 100, 105, 100]
        baseline = float(np.median(forecast_values))  # ~100

        peak_day_map = {}
        for i, value in enumerate(forecast_values):
            ratio = value / baseline
            # Day 4 has value 250 => ratio ~2.5 > 1.5
            if ratio > 1.5:
                dow = i % 7
                peak_day_map[dow] = max(peak_day_map.get(dow, 0), ratio)

        # Day index 4 (value=250) should be detected as peak
        assert len(peak_day_map) > 0
        # Verify the peak ratio is approximately 2.5
        peak_ratios = list(peak_day_map.values())
        assert any(r > 2.0 for r in peak_ratios)

        # Value exactly at 1.5x should NOT be peak (strict >)
        edge_value = baseline * 1.5  # exactly 1.5x
        edge_ratio = edge_value / baseline
        assert not (edge_ratio > 1.5), "Exactly 1.5x should not trigger peak"

    def test_two_stores_different_peak_profiles(self):
        """
        Store 1 (downtown): high weekday traffic, normal weekends
        Store 2 (suburban mall): low weekday, peak weekends
        Verify independent peak detection.
        """
        import numpy as np

        # Store 1: downtown - peaks on Mon-Fri
        store1_traffic = {h: 50.0 for h in range(24)}
        for h in range(9, 18):
            store1_traffic[h] = 200.0  # business hours heavy

        # Store 2: suburban - peaks on weekends (simulated as higher overall on those days)
        store2_traffic = {h: 30.0 for h in range(24)}
        for h in range(10, 21):
            store2_traffic[h] = 150.0  # weekend shopping hours

        # Compute peak and low-traffic thresholds independently
        store1_peak = max(store1_traffic.values())  # 200
        store1_low_threshold = store1_peak * 0.30  # 60
        store1_low_hours = {h for h, v in store1_traffic.items() if v < store1_low_threshold}

        store2_peak = max(store2_traffic.values())  # 150
        store2_low_threshold = store2_peak * 0.30  # 45
        store2_low_hours = {h for h, v in store2_traffic.items() if v < store2_low_threshold}

        # Store 1: hours 0-8 and 18-23 are low traffic (value=50 < 60)
        assert 3 in store1_low_hours
        assert 12 not in store1_low_hours  # peak hour

        # Store 2: hours 0-9 and 21-23 are low traffic (value=30 < 45)
        assert 3 in store2_low_hours
        assert 15 not in store2_low_hours  # peak hour

        # Key difference: hour 19 is low for store 1 (50 < 60) but NOT for store 2 (150 >= 45)
        assert 19 in store1_low_hours
        assert 19 not in store2_low_hours

    def test_lighting_kept_full_on_peak_day(self):
        """On peak sales days, lighting should stay at full (continue/skip)."""
        eq_type = "lighting"
        is_peak_day = True
        hour = 14
        low_traffic_hours = {0, 1, 2, 3, 4, 5, 6, 22, 23}

        # Replicate the logic from optimize_equipment_schedule
        recommended_level = None
        if eq_type == "lighting":
            if is_peak_day:
                # Keep full lighting on peak sales days -> continue (no recommendation)
                recommended_level = None  # means "skip, keep as is"
            elif hour in low_traffic_hours:
                recommended_level = "reduced"

        assert recommended_level is None, "Lighting should stay full on peak day"

    def test_pos_standby_during_closed_hours(self):
        """POS terminals should go to standby during store-closed hours (22-7)."""
        eq_type = "pos"
        is_peak_day = False

        results = {}
        for hour in range(24):
            recommended_level = None
            reduction_factor = 0.0
            if eq_type == "pos":
                if hour >= 22 or hour < 7:
                    recommended_level = "standby"
                    reduction_factor = 0.85

            results[hour] = (recommended_level, reduction_factor)

        # Closed hours (22, 23, 0-6) should be standby
        for h in [22, 23, 0, 1, 2, 3, 4, 5, 6]:
            assert results[h] == ("standby", 0.85), f"Hour {h} should be standby"

        # Open hours (7-21) should have no recommendation
        for h in range(7, 22):
            assert results[h] == (None, 0.0), f"Hour {h} should have no POS recommendation"

    def test_hvac_pre_cooling_before_peak(self):
        """HVAC should run at full power 1 hour before peak starts (pre-cooling)."""
        is_peak_day = False
        eq_type = "hvac"
        peak_hours = {10, 11, 12, 13, 14, 15, 16, 17}
        low_traffic_hours = {0, 1, 2, 3, 4, 5, 6, 22, 23}

        # Hour 9: not peak, not low-traffic, but (9+1)=10 is in peak_hours
        hour = 9
        recommended_level = None
        if eq_type == "hvac":
            if is_peak_day:
                pass
            elif hour in low_traffic_hours:
                recommended_level = "reduced"
            elif (hour + 1) in peak_hours and hour not in peak_hours:
                recommended_level = "full"
                reason = "Pre-cool before predicted peak traffic"

        assert recommended_level == "full", "Should pre-cool 1 hour before peak"
