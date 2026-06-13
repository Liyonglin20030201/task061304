import pytest
import numpy as np
from app.services.forecast_service import _stl_decompose, _extrapolate_trend, _extrapolate_seasonal, _rolling_backtest


class TestSTLDecomposition:
    def test_decomposes_into_three_components(self):
        np.random.seed(42)
        n = 56
        trend = np.linspace(100, 120, n)
        seasonal = np.tile([10, -5, 3, -2, 8, -3, -11], n // 7)
        noise = np.random.normal(0, 2, n)
        values = trend + seasonal + noise

        t, s, r = _stl_decompose(values, period=7)
        assert len(t) == n
        assert len(s) == n
        assert len(r) == n
        reconstructed = t + s + r
        np.testing.assert_allclose(reconstructed, values, atol=1e-10)

    def test_short_data_fallback(self):
        values = np.array([100, 110, 105, 115, 108])
        t, s, r = _stl_decompose(values, period=7)
        assert len(t) == 5
        assert all(np.isfinite(t))

    def test_seasonal_sums_near_zero(self):
        np.random.seed(0)
        values = np.random.normal(100, 10, 42)
        _, s, _ = _stl_decompose(values, period=7)
        seasonal_cycle = s[:7]
        assert abs(np.sum(seasonal_cycle)) < 5


class TestTrendExtrapolation:
    def test_damped_trend(self):
        trend = np.linspace(100, 114, 14)
        forecast = _extrapolate_trend(trend, 7)
        assert len(forecast) == 7
        # slope should be positive but dampened
        diffs = np.diff(forecast)
        assert all(d > 0 for d in diffs)
        assert diffs[-1] < diffs[0]  # dampening effect


class TestSeasonalExtrapolation:
    def test_repeats_pattern(self):
        seasonal = np.array([5, -3, 2, -1, 4, -2, -5.0] * 4)
        forecast = _extrapolate_seasonal(seasonal, 14, period=7)
        assert len(forecast) == 14
        np.testing.assert_array_almost_equal(forecast[:7], forecast[7:14])


class TestBacktest:
    def test_basic_backtest(self):
        np.random.seed(42)
        n = 60
        trend = np.linspace(100, 120, n)
        seasonal = np.tile([5, -3, 2, -1, 4, -2, -5], n // 7 + 1)[:n]
        values = trend + seasonal + np.random.normal(0, 2, n)
        result = _rolling_backtest(values)
        assert result["mape"] is not None
        assert result["rmse"] is not None
        assert result["mape"] < 30  # reasonable accuracy

    def test_insufficient_data(self):
        values = np.array([100, 110, 105])
        result = _rolling_backtest(values)
        assert result["mape"] is None
