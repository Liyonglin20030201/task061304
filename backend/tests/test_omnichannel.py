import pytest
from datetime import date, timedelta


class TestChannelKPIs:
    """Tests for omnichannel KPI aggregation logic."""

    def _aggregate_by_channel(self, orders: list) -> dict:
        """Sum GMV per channel."""
        channel_gmv = {}
        for order in orders:
            ch = order["channel"]
            channel_gmv[ch] = channel_gmv.get(ch, 0.0) + order["amount"]
        return channel_gmv

    def _count_distinct_receipts(self, orders: list) -> int:
        """Count unique receipt IDs."""
        return len(set(o["receipt_id"] for o in orders))

    def _avg_ticket(self, gmv: float, order_count: int) -> float:
        if order_count == 0:
            return 0.0
        return round(gmv / order_count, 2)

    def _growth_rate(self, current: float, previous: float) -> float:
        if previous == 0:
            return 0.0
        return round((current - previous) / previous * 100, 2)

    def test_aggregate_by_channel(self):
        orders = [
            {"channel": "online", "amount": 200.0, "receipt_id": "R001"},
            {"channel": "online", "amount": 150.0, "receipt_id": "R002"},
            {"channel": "offline", "amount": 300.0, "receipt_id": "R003"},
            {"channel": "offline", "amount": 250.0, "receipt_id": "R004"},
            {"channel": "online", "amount": 100.0, "receipt_id": "R005"},
        ]
        result = self._aggregate_by_channel(orders)
        assert result["online"] == pytest.approx(450.0)
        assert result["offline"] == pytest.approx(550.0)

    def test_order_count_distinct_receipts(self):
        orders = [
            {"channel": "online", "amount": 50.0, "receipt_id": "R001"},
            {"channel": "online", "amount": 30.0, "receipt_id": "R001"},  # same receipt
            {"channel": "offline", "amount": 100.0, "receipt_id": "R002"},
        ]
        count = self._count_distinct_receipts(orders)
        assert count == 2

    def test_avg_ticket(self):
        gmv = 10000.0
        order_count = 40
        result = self._avg_ticket(gmv, order_count)
        assert result == 250.0

    def test_growth_rate(self):
        current = 12000.0
        previous = 10000.0
        rate = self._growth_rate(current, previous)
        assert rate == 20.0


class TestAttributionModels:
    """Tests for multi-channel marketing attribution models."""

    def _attribute(self, touchpoints: list, model: str = "last_touch") -> dict:
        """
        touchpoints: list of dicts with 'channel' key, ordered chronologically.
        Returns dict of channel -> attribution percentage.
        """
        if not touchpoints:
            return {}

        if len(touchpoints) == 1:
            return {touchpoints[0]["channel"]: 100.0}

        if model == "last_touch":
            return {touchpoints[-1]["channel"]: 100.0}

        elif model == "first_touch":
            return {touchpoints[0]["channel"]: 100.0}

        elif model == "linear":
            n = len(touchpoints)
            share = round(100.0 / n, 1)
            result = {}
            for tp in touchpoints:
                ch = tp["channel"]
                result[ch] = result.get(ch, 0.0) + share
            # Adjust rounding
            return {k: round(v, 1) for k, v in result.items()}

        elif model == "time_decay":
            # Exponential decay: more recent touchpoints get higher weight
            n = len(touchpoints)
            decay_factor = 0.5
            weights = []
            for i in range(n):
                weights.append(decay_factor ** (n - 1 - i))
            total_weight = sum(weights)
            result = {}
            for i, tp in enumerate(touchpoints):
                ch = tp["channel"]
                pct = round(weights[i] / total_weight * 100, 1)
                result[ch] = result.get(ch, 0.0) + pct
            return {k: round(v, 1) for k, v in result.items()}

        return {}

    def _attribute_no_touchpoints(self, conversion_channel: str) -> dict:
        """Conversion without prior events gives 100% to conversion channel."""
        return {conversion_channel: 100.0}

    def test_last_touch(self):
        touchpoints = [
            {"channel": "online", "event": "browse"},
            {"channel": "offline", "event": "purchase"},
        ]
        result = self._attribute(touchpoints, model="last_touch")
        assert result == {"offline": 100.0}

    def test_first_touch(self):
        touchpoints = [
            {"channel": "online", "event": "browse"},
            {"channel": "offline", "event": "purchase"},
        ]
        result = self._attribute(touchpoints, model="first_touch")
        assert result == {"online": 100.0}

    def test_linear(self):
        touchpoints = [
            {"channel": "social", "event": "ad_click"},
            {"channel": "online", "event": "browse"},
            {"channel": "offline", "event": "purchase"},
        ]
        result = self._attribute(touchpoints, model="linear")
        assert result["social"] == pytest.approx(33.3, abs=0.2)
        assert result["online"] == pytest.approx(33.3, abs=0.2)
        assert result["offline"] == pytest.approx(33.3, abs=0.2)

    def test_time_decay(self):
        touchpoints = [
            {"channel": "social", "event": "ad_click"},
            {"channel": "online", "event": "browse"},
            {"channel": "offline", "event": "purchase"},
        ]
        result = self._attribute(touchpoints, model="time_decay")
        # Closer (later) touchpoints should have more weight
        assert result["offline"] > result["online"]
        assert result["online"] > result["social"]

    def test_single_touchpoint(self):
        touchpoints = [{"channel": "online", "event": "purchase"}]
        for model in ["last_touch", "first_touch", "linear", "time_decay"]:
            result = self._attribute(touchpoints, model=model)
            assert result == {"online": 100.0}

    def test_no_touchpoints(self):
        result = self._attribute_no_touchpoints("offline")
        assert result == {"offline": 100.0}


class TestConversionFunnel:
    """Tests for omnichannel conversion funnel analysis."""

    def _build_funnel(self, events_by_step: list) -> list:
        """
        events_by_step: list of dicts with 'step_name' and 'count'.
        Returns list of dicts with step_name, count, and conversion_rate.
        """
        funnel = []
        for i, step in enumerate(events_by_step):
            entry = {
                "step_name": step["step_name"],
                "count": step["count"],
            }
            if i == 0:
                entry["conversion_rate"] = None
            else:
                prev_count = events_by_step[i - 1]["count"]
                if prev_count == 0:
                    entry["conversion_rate"] = 0.0
                else:
                    entry["conversion_rate"] = round(
                        step["count"] / prev_count * 100, 2
                    )
            funnel.append(entry)
        return funnel

    def test_funnel_decreasing(self):
        steps = [
            {"step_name": "visit", "count": 1000},
            {"step_name": "add_to_cart", "count": 400},
            {"step_name": "checkout", "count": 200},
            {"step_name": "purchase", "count": 150},
        ]
        funnel = self._build_funnel(steps)
        for i in range(1, len(funnel)):
            assert funnel[i]["count"] <= funnel[i - 1]["count"]

    def test_conversion_rate_calculation(self):
        steps = [
            {"step_name": "visit", "count": 1000},
            {"step_name": "add_to_cart", "count": 400},
            {"step_name": "purchase", "count": 200},
        ]
        funnel = self._build_funnel(steps)
        assert funnel[1]["conversion_rate"] == 40.0
        assert funnel[2]["conversion_rate"] == 50.0

    def test_first_step_no_rate(self):
        steps = [
            {"step_name": "visit", "count": 500},
            {"step_name": "purchase", "count": 100},
        ]
        funnel = self._build_funnel(steps)
        assert funnel[0]["conversion_rate"] is None

    def test_empty_channel(self):
        steps = [
            {"step_name": "visit", "count": 0},
            {"step_name": "add_to_cart", "count": 0},
            {"step_name": "purchase", "count": 0},
        ]
        funnel = self._build_funnel(steps)
        assert all(f["count"] == 0 for f in funnel)
        assert funnel[1]["conversion_rate"] == 0.0


class TestMemberOverlap:
    """Tests for member channel overlap analysis."""

    def _compute_overlap(self, online_members: set, offline_members: set) -> dict:
        """Compute member overlap between online and offline channels."""
        online_only = online_members - offline_members
        offline_only = offline_members - online_members
        both = online_members & offline_members
        total = online_members | offline_members
        return {
            "online_only": len(online_only),
            "offline_only": len(offline_only),
            "both_channels": len(both),
            "total": len(total),
        }

    def test_exclusive_online(self):
        online = {"M001", "M002", "M003"}
        offline = {"M004", "M005"}
        result = self._compute_overlap(online, offline)
        assert result["online_only"] == 3

    def test_exclusive_offline(self):
        online = {"M001"}
        offline = {"M002", "M003", "M004"}
        result = self._compute_overlap(online, offline)
        assert result["offline_only"] == 3

    def test_both_channels(self):
        online = {"M001", "M002", "M003"}
        offline = {"M002", "M003", "M004"}
        result = self._compute_overlap(online, offline)
        assert result["both_channels"] == 2

    def test_total_correct(self):
        online = {"M001", "M002", "M003", "M005"}
        offline = {"M002", "M003", "M004"}
        result = self._compute_overlap(online, offline)
        assert result["online_only"] + result["offline_only"] + result["both_channels"] == result["total"]
        assert result["total"] == 5


class TestUnifiedMemberStats:
    """Tests for unified member statistics across channels."""

    def _cross_channel_percentage(self, both_count: int, total_members: int) -> float:
        """Percentage of members active in multiple channels."""
        if total_members == 0:
            return 0.0
        return round(both_count / total_members * 100, 2)

    def _avg_frequency(self, total_orders: int, total_members: int) -> float:
        """Average purchase frequency per member."""
        if total_members == 0:
            return 0.0
        return round(total_orders / total_members, 2)

    def _avg_recency(self, member_last_purchases: list, reference_date: date) -> float:
        """Average days since last purchase across members."""
        if not member_last_purchases:
            return 0.0
        days = []
        for last_purchase in member_last_purchases:
            if isinstance(last_purchase, str):
                last_purchase = date.fromisoformat(last_purchase)
            delta = (reference_date - last_purchase).days
            days.append(delta)
        return round(sum(days) / len(days), 2)

    def test_cross_channel_percentage(self):
        both_count = 150
        total_members = 500
        pct = self._cross_channel_percentage(both_count, total_members)
        assert pct == 30.0

    def test_avg_frequency(self):
        total_orders = 2400
        total_members = 800
        freq = self._avg_frequency(total_orders, total_members)
        assert freq == 3.0

    def test_avg_recency(self):
        reference = date(2026, 6, 14)
        last_purchases = [
            date(2026, 6, 10),  # 4 days
            date(2026, 6, 7),   # 7 days
            date(2026, 6, 4),   # 10 days
            date(2026, 6, 1),   # 13 days
        ]
        avg = self._avg_recency(last_purchases, reference)
        # (4 + 7 + 10 + 13) / 4 = 8.5
        assert avg == 8.5
