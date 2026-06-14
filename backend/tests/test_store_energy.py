import pytest
import math
from datetime import date, timedelta


class TestEnergyKPICalculation:
    """Tests for store energy KPI computation logic."""

    def _sum_daily_kwh(self, readings: list) -> float:
        return sum(r["kwh"] for r in readings)

    def _calculate_cost(self, kwh: float, rate: float) -> float:
        return round(kwh * rate, 2)

    def _cost_per_sqm(self, total_cost: float, store_area: float) -> float:
        if store_area <= 0:
            return 0.0
        return round(total_cost / store_area, 4)

    def _revenue_per_kwh(self, total_revenue: float, total_kwh: float) -> float:
        if total_kwh <= 0:
            return 0.0
        return round(total_revenue / total_kwh, 4)

    def _period_comparison(self, current: float, previous: float) -> float:
        if previous == 0:
            return 0.0
        return round((current - previous) / previous * 100, 2)

    def test_total_kwh_sum(self):
        readings = [
            {"date": "2026-06-01", "kwh": 120.5},
            {"date": "2026-06-02", "kwh": 135.2},
            {"date": "2026-06-03", "kwh": 118.8},
            {"date": "2026-06-04", "kwh": 142.0},
            {"date": "2026-06-05", "kwh": 130.0},
        ]
        total = self._sum_daily_kwh(readings)
        assert total == pytest.approx(646.5)

    def test_cost_calculation(self):
        kwh = 500.0
        rate = 0.85
        cost = self._calculate_cost(kwh, rate)
        assert cost == 425.0

    def test_cost_per_sqm(self):
        total_cost = 850.0
        store_area = 200.0
        result = self._cost_per_sqm(total_cost, store_area)
        assert result == 4.25

    def test_revenue_per_kwh(self):
        total_revenue = 50000.0
        total_kwh = 2500.0
        result = self._revenue_per_kwh(total_revenue, total_kwh)
        assert result == 20.0

    def test_period_comparison(self):
        current_kwh = 2800.0
        previous_kwh = 2500.0
        change_pct = self._period_comparison(current_kwh, previous_kwh)
        assert change_pct == 12.0


class TestPeakHourAnalysis:
    """Tests for 24-hour peak energy distribution analysis."""

    def _compute_hourly_distribution(self, readings: list) -> list:
        """Aggregate kwh readings into 24-hour buckets."""
        distribution = [0.0] * 24
        for r in readings:
            hour = r["hour"]
            if 0 <= hour < 24:
                distribution[hour] += r["kwh"]
        return distribution

    def _identify_peak_hour(self, distribution: list) -> int:
        if not distribution or all(v == 0 for v in distribution):
            return -1
        return distribution.index(max(distribution))

    def test_24_hour_distribution(self):
        readings = [{"hour": h, "kwh": 10.0 + h * 0.5} for h in range(24)]
        distribution = self._compute_hourly_distribution(readings)
        assert len(distribution) == 24

    def test_peak_identification(self):
        readings = [{"hour": h, "kwh": 10.0} for h in range(24)]
        readings.append({"hour": 14, "kwh": 50.0})  # spike at hour 14
        distribution = self._compute_hourly_distribution(readings)
        peak = self._identify_peak_hour(distribution)
        assert peak == 14

    def test_empty_readings(self):
        distribution = self._compute_hourly_distribution([])
        assert len(distribution) == 24
        assert all(v == 0.0 for v in distribution)


class TestAnomalyDetection:
    """Tests for energy anomaly detection using statistical thresholds."""

    def _detect_anomalies(self, readings: list, window: int = None, sigma_threshold: float = 2.0) -> list:
        """Flag readings that exceed mean + sigma_threshold * std.
        Uses leave-one-out: each point is tested against statistics of the remaining points.
        """
        if len(readings) < 3:
            return []

        if window is not None:
            baseline_source = readings[-window:] if len(readings) > window else list(readings)
        else:
            baseline_source = list(readings)

        n = len(baseline_source)
        total = sum(baseline_source)
        total_sq = sum(x ** 2 for x in baseline_source)

        anomalies = []
        for i, val in enumerate(readings):
            # Leave-one-out statistics (exclude the current point from baseline)
            if val in baseline_source and n > 2:
                loo_n = n - 1
                loo_total = total - val
                loo_total_sq = total_sq - val ** 2
            else:
                loo_n = n
                loo_total = total
                loo_total_sq = total_sq

            if loo_n < 2:
                continue

            mean = loo_total / loo_n
            variance = loo_total_sq / loo_n - mean ** 2
            if variance < 0:
                variance = 0
            std = math.sqrt(variance)

            if std == 0:
                continue

            if abs(val - mean) > sigma_threshold * std:
                anomalies.append(i)

        return anomalies

    def test_normal_readings_no_anomaly(self):
        readings = [100, 102, 98, 101, 99, 103, 97, 100, 101, 99]
        anomalies = self._detect_anomalies(readings, sigma_threshold=3.0)
        assert len(anomalies) == 0

    def test_spike_detected(self):
        readings = [100, 102, 98, 101, 99, 103, 97, 100, 101, 400]
        anomalies = self._detect_anomalies(readings, sigma_threshold=3.0)
        assert 9 in anomalies

    def test_rolling_window(self):
        # Old spike should not affect baseline when window is small
        readings = [500, 100, 102, 98, 101, 99, 103, 97, 100, 101, 99]
        anomalies = self._detect_anomalies(readings, window=5, sigma_threshold=2.0)
        # Index 0 (500) is outside the window baseline, but still tested against recent baseline
        assert 0 in anomalies

    def test_zero_std_handling(self):
        # All constant readings - std is 0, should not crash
        readings = [100, 100, 100, 100, 100]
        anomalies = self._detect_anomalies(readings, sigma_threshold=2.0)
        assert anomalies == []


class TestScheduleOptimization:
    """Tests for HVAC/lighting schedule optimization based on traffic patterns."""

    def _optimize_schedule(
        self,
        hourly_traffic: list,
        store_open: int,
        store_close: int,
        equipment_type: str = "hvac",
    ) -> list:
        """
        Returns a 24-element list of scheduling levels:
        'off', 'standby', 'reduced', 'full'
        """
        if not hourly_traffic or len(hourly_traffic) != 24:
            return ["off"] * 24

        peak_traffic = max(hourly_traffic)
        if peak_traffic == 0:
            peak_traffic = 1

        schedule = []
        for hour in range(24):
            if hour < store_open or hour >= store_close:
                if equipment_type == "refrigeration":
                    schedule.append("full")
                else:
                    schedule.append("standby")
            elif equipment_type == "refrigeration":
                schedule.append("full")
            else:
                traffic_ratio = hourly_traffic[hour] / peak_traffic
                # Pre-cooling: 1 hour before predicted peak
                peak_hour = hourly_traffic.index(max(hourly_traffic))
                if hour == peak_hour - 1:
                    schedule.append("full")
                elif traffic_ratio < 0.30:
                    schedule.append("reduced")
                else:
                    schedule.append("full")
        return schedule

    def _calculate_savings(
        self, reduced_hours: int, power_kw: float, reduction_pct: float, rate: float
    ) -> float:
        return round(reduced_hours * power_kw * reduction_pct * rate, 2)

    def test_low_traffic_hours_reduced(self):
        traffic = [0] * 24
        # Store open 6-22, peak at hour 14
        for h in range(6, 22):
            traffic[h] = 10
        traffic[14] = 100  # peak
        # Hours with traffic_ratio < 0.30 (i.e., 10/100 = 0.10) get "reduced"
        schedule = self._optimize_schedule(traffic, store_open=6, store_close=22)
        # Hour 10 has traffic=10, ratio=0.10 < 0.30
        assert schedule[10] == "reduced"

    def test_hvac_pre_cooling(self):
        traffic = [0] * 24
        for h in range(6, 22):
            traffic[h] = 50
        traffic[15] = 200  # peak at 15
        schedule = self._optimize_schedule(traffic, store_open=6, store_close=22)
        # 1 hour before peak (hour 14) should be "full"
        assert schedule[14] == "full"

    def test_refrigeration_constant(self):
        traffic = [0] * 24
        for h in range(6, 22):
            traffic[h] = 50
        traffic[14] = 200
        schedule = self._optimize_schedule(
            traffic, store_open=6, store_close=22, equipment_type="refrigeration"
        )
        assert all(level == "full" for level in schedule)

    def test_closed_hours_standby(self):
        traffic = [0] * 24
        for h in range(6, 22):
            traffic[h] = 50
        traffic[14] = 100
        schedule = self._optimize_schedule(traffic, store_open=6, store_close=22)
        # Hours 0-5 are before open
        for h in range(0, 6):
            assert schedule[h] in ("off", "standby")

    def test_savings_calculation(self):
        reduced_hours = 8
        power_kw = 50.0
        reduction_pct = 0.40
        rate = 0.85
        savings = self._calculate_savings(reduced_hours, power_kw, reduction_pct, rate)
        # 8 * 50 * 0.40 * 0.85 = 136.0
        assert savings == 136.0


class TestBudgetAlerts:
    """Tests for monthly energy budget alert generation."""

    def _check_budget_alert(self, usage_pct: float, threshold: float = 0.80) -> str:
        """Return alert level based on usage percentage of budget."""
        if usage_pct >= 1.0:
            return "critical"
        elif usage_pct >= threshold:
            return "warning"
        else:
            return "none"

    def _aggregate_month(self, daily_readings: list, year: int, month: int) -> float:
        """Sum only readings within the specified year/month."""
        total = 0.0
        for r in daily_readings:
            d = r["date"] if isinstance(r["date"], date) else date.fromisoformat(r["date"])
            if d.year == year and d.month == month:
                total += r["kwh"]
        return total

    def test_below_threshold_no_alert(self):
        usage_pct = 0.60
        alert = self._check_budget_alert(usage_pct, threshold=0.80)
        assert alert == "none"

    def test_at_threshold_warning(self):
        usage_pct = 0.80
        alert = self._check_budget_alert(usage_pct, threshold=0.80)
        assert alert == "warning"

    def test_exceeded_critical(self):
        usage_pct = 1.05
        alert = self._check_budget_alert(usage_pct, threshold=0.80)
        assert alert == "critical"

    def test_correct_year_month_aggregation(self):
        daily_readings = [
            {"date": "2026-05-30", "kwh": 100.0},
            {"date": "2026-05-31", "kwh": 110.0},
            {"date": "2026-06-01", "kwh": 120.0},
            {"date": "2026-06-02", "kwh": 130.0},
            {"date": "2026-06-03", "kwh": 125.0},
            {"date": "2026-07-01", "kwh": 140.0},
        ]
        june_total = self._aggregate_month(daily_readings, 2026, 6)
        assert june_total == pytest.approx(375.0)


class TestWeatherCorrelation:
    """Tests for weather-energy correlation analysis."""

    def _pearson_r(self, x: list, y: list):
        """Calculate Pearson correlation coefficient. Returns None if insufficient data."""
        n = len(x)
        if n < 3 or n != len(y):
            return None

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
        std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

        if std_x == 0 or std_y == 0:
            return None

        return round(cov / (std_x * std_y), 4)

    def test_positive_correlation(self):
        # Higher temperature -> higher kWh (HVAC cooling load)
        temps = [20, 25, 30, 35, 40]
        kwh = [100, 130, 160, 200, 250]
        r = self._pearson_r(temps, kwh)
        assert r is not None
        assert r > 0.9

    def test_no_correlation(self):
        # Unrelated data
        temps = [15, 20, 25, 30, 35, 40, 22, 28]
        kwh = [150, 100, 200, 90, 180, 110, 160, 130]
        r = self._pearson_r(temps, kwh)
        assert r is not None
        assert abs(r) < 0.5

    def test_insufficient_data(self):
        temps = [20, 25]
        kwh = [100, 130]
        r = self._pearson_r(temps, kwh)
        assert r is None
