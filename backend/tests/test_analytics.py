import pytest
import numpy as np
from app.services.forecast_service import _holt_winters_forecast


class TestHoltWinters:
    def test_basic_forecast(self):
        values = np.array([100, 110, 105, 115, 108, 120, 112,
                          105, 115, 110, 120, 113, 125, 117,
                          110, 120, 115, 125, 118, 130, 122])
        forecast, lower, upper = _holt_winters_forecast(values, periods=7)
        assert len(forecast) == 7
        assert len(lower) == 7
        assert len(upper) == 7
        assert all(f > 0 for f in forecast)
        assert all(l <= f <= u for l, f, u in zip(lower, forecast, upper))

    def test_insufficient_data(self):
        values = np.array([100, 110, 105, 115, 108])
        forecast, lower, upper = _holt_winters_forecast(values, periods=5)
        assert len(forecast) == 5
        assert all(f >= 0 for f in forecast)

    def test_confidence_interval_widens(self):
        values = np.random.normal(100, 10, 50)
        forecast, lower, upper = _holt_winters_forecast(values, periods=14)
        widths = upper - lower
        assert widths[-1] >= widths[0]
