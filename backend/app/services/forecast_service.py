import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date, timedelta


async def get_sales_forecast(db: AsyncSession, store_id: int, periods: int = 30) -> dict:
    sql = """
    SELECT sale_date, SUM(total_amount) as daily_sales
    FROM sales
    WHERE store_id = :sid AND sale_date >= CURRENT_DATE - INTERVAL '180 days'
    GROUP BY sale_date
    ORDER BY sale_date
    """
    result = await db.execute(text(sql), {"sid": store_id})
    rows = result.fetchall()

    if len(rows) < 14:
        return {"error": "历史数据不足，至少需要14天数据", "store_id": store_id}

    dates = [row[0] for row in rows]
    values = np.array([float(row[1]) for row in rows])

    trend, seasonal, residual = _stl_decompose(values, period=7)

    forecast_trend = _extrapolate_trend(trend, periods)
    forecast_seasonal = _extrapolate_seasonal(seasonal, periods, period=7)
    forecast_residual = np.full(periods, np.mean(residual[-14:]))

    forecast_values = forecast_trend + forecast_seasonal + forecast_residual

    promo_sql = """
    SELECT start_date, end_date, discount_rate, discount_amount, promo_type
    FROM promotions
    WHERE store_id = :sid AND end_date >= CURRENT_DATE AND status = 'active'
    """
    promo_result = await db.execute(text(promo_sql), {"sid": store_id})
    promos = promo_result.fetchall()

    historical_promo_sql = """
    SELECT p.start_date, p.end_date, p.discount_rate, p.promo_type,
        AVG(s.total_amount) as promo_avg,
        (SELECT AVG(sub.total_amount) FROM (
            SELECT SUM(total_amount) as total_amount FROM sales
            WHERE store_id = :sid AND sale_date BETWEEN p.start_date - INTERVAL '14 days' AND p.start_date - INTERVAL '1 day'
            GROUP BY sale_date
        ) sub) as baseline_avg
    FROM promotions p
    JOIN sales s ON s.store_id = p.store_id AND s.sale_date BETWEEN p.start_date AND p.end_date
    WHERE p.store_id = :sid AND p.status = 'completed'
    GROUP BY p.id, p.start_date, p.end_date, p.discount_rate, p.promo_type
    ORDER BY p.end_date DESC
    LIMIT 10
    """
    hist_promo_result = await db.execute(text(historical_promo_sql), {"sid": store_id})
    hist_promos = hist_promo_result.fetchall()

    promo_lift = _calculate_promo_lift(hist_promos)

    last_date = dates[-1]
    forecast_dates = []
    for i in range(periods):
        forecast_dates.append((last_date + timedelta(days=i + 1)).isoformat())

    for promo in promos:
        p_start, p_end, p_discount_rate, p_discount_amount, p_type = promo
        lift = promo_lift.get(p_type, _estimate_lift(p_discount_rate, p_discount_amount))
        for i, fd in enumerate(forecast_dates):
            fd_date = date.fromisoformat(fd)
            if p_start <= fd_date <= p_end:
                days_into = (fd_date - p_start).days
                duration = (p_end - p_start).days + 1
                decay = 1.0 - 0.3 * (days_into / max(duration, 1))
                forecast_values[i] *= (1.0 + lift * max(decay, 0.5))

    weather_sql = """
    SELECT w.weather_date, w.precipitation, w.temp_high, w.temp_low
    FROM weather w
    JOIN stores st ON st.city = w.city
    WHERE st.id = :sid AND w.weather_date > CURRENT_DATE
    ORDER BY w.weather_date
    LIMIT :periods
    """
    weather_result = await db.execute(text(weather_sql), {"sid": store_id, "periods": periods})
    weather_rows = weather_result.fetchall()

    if weather_rows:
        for i, wrow in enumerate(weather_rows):
            if i < len(forecast_values):
                precip = float(wrow[1]) if wrow[1] else 0
                temp_high = float(wrow[2]) if wrow[2] else 25
                if precip > 30:
                    forecast_values[i] *= 0.80
                elif precip > 15:
                    forecast_values[i] *= 0.88
                elif precip > 5:
                    forecast_values[i] *= 0.94
                if temp_high > 38 or temp_high < -5:
                    forecast_values[i] *= 0.90

    forecast_values = np.maximum(forecast_values, 0)

    residual_std = np.std(residual[-30:]) if len(residual) >= 30 else np.std(residual)
    confidence_factor = np.sqrt(np.arange(1, periods + 1) * 0.08 + 1)
    confidence_lower = forecast_values - 1.96 * residual_std * confidence_factor
    confidence_upper = forecast_values + 1.96 * residual_std * confidence_factor
    confidence_lower = np.maximum(confidence_lower, 0)

    backtesting = _rolling_backtest(values)

    return {
        "store_id": store_id,
        "historical": [{"date": d.isoformat(), "value": round(float(v), 2)} for d, v in zip(dates[-30:], values[-30:])],
        "decomposition": {
            "trend_last": round(float(trend[-1]), 2),
            "seasonal_pattern": [round(float(s), 2) for s in seasonal[-7:]],
            "residual_std": round(float(residual_std), 2),
        },
        "forecast": [
            {
                "date": forecast_dates[i],
                "value": round(float(forecast_values[i]), 2),
                "lower": round(float(confidence_lower[i]), 2),
                "upper": round(float(confidence_upper[i]), 2),
            }
            for i in range(periods)
        ],
        "metrics": backtesting,
        "promo_lift_factors": promo_lift,
    }


def _stl_decompose(values: np.ndarray, period: int = 7, iterations: int = 3):
    n = len(values)
    if n < period * 2:
        trend = np.full(n, np.mean(values))
        seasonal = np.zeros(n)
        residual = values - trend
        return trend, seasonal, residual

    trend = np.copy(values).astype(float)

    kernel_size = period if period % 2 == 1 else period + 1
    for _ in range(iterations):
        kernel = np.ones(kernel_size) / kernel_size
        padded = np.pad(trend, (kernel_size // 2, kernel_size // 2), mode="edge")
        trend = np.convolve(padded, kernel, mode="valid")[:n]

    detrended = values - trend

    seasonal = np.zeros(n)
    for i in range(period):
        cycle_values = detrended[i::period]
        seasonal[i::period] = np.mean(cycle_values)

    seasonal_mean = np.mean(seasonal[:period])
    seasonal -= seasonal_mean

    residual = values - trend - seasonal

    return trend, seasonal, residual


def _extrapolate_trend(trend: np.ndarray, periods: int) -> np.ndarray:
    n = len(trend)
    window = min(14, n)
    recent_trend = trend[-window:]

    x = np.arange(window)
    coeffs = np.polyfit(x, recent_trend, 1)
    slope = coeffs[0]

    dampening = 0.95
    forecast = np.zeros(periods)
    last_val = trend[-1]
    for i in range(periods):
        damped_slope = slope * (dampening ** i)
        last_val += damped_slope
        forecast[i] = last_val

    return forecast


def _extrapolate_seasonal(seasonal: np.ndarray, periods: int, period: int = 7) -> np.ndarray:
    n = len(seasonal)
    last_cycle = seasonal[-(period + n % period):][-period:] if n >= period else seasonal
    forecast = np.tile(last_cycle, (periods // period) + 1)[:periods]
    return forecast


def _calculate_promo_lift(hist_promos) -> dict:
    lift_by_type = {}
    for row in hist_promos:
        p_start, p_end, p_rate, p_type, promo_avg, baseline_avg = row
        if baseline_avg and baseline_avg > 0 and promo_avg:
            lift = (float(promo_avg) - float(baseline_avg)) / float(baseline_avg)
            lift_by_type.setdefault(p_type, []).append(max(lift, 0))

    result = {}
    for ptype, lifts in lift_by_type.items():
        if lifts:
            result[ptype] = round(float(np.mean(lifts)), 3)
    return result


def _estimate_lift(discount_rate, discount_amount) -> float:
    if discount_rate and float(discount_rate) > 0:
        return min(float(discount_rate) * 0.8, 0.6)
    if discount_amount and float(discount_amount) > 0:
        return 0.15
    return 0.10


def _rolling_backtest(values: np.ndarray, window: int = 7) -> dict:
    n = len(values)
    if n < window * 4:
        return {"mape": None, "rmse": None, "message": "数据不足以进行回测"}

    test_start = n - window
    train = values[:test_start]
    test = values[test_start:]

    trend, seasonal, residual = _stl_decompose(train, period=7)
    forecast_trend = _extrapolate_trend(trend, window)
    forecast_seasonal = _extrapolate_seasonal(seasonal, window, period=7)
    forecast_residual = np.full(window, np.mean(residual[-14:]))
    forecast = forecast_trend + forecast_seasonal + forecast_residual
    forecast = np.maximum(forecast, 0)

    abs_errors = np.abs(forecast - test)
    pct_errors = abs_errors / np.where(test > 0, test, 1)
    mape = float(np.mean(pct_errors)) * 100
    rmse = float(np.sqrt(np.mean(abs_errors ** 2)))

    return {
        "mape": round(mape, 2),
        "rmse": round(rmse, 2),
        "confidence_level": "95%",
        "method": "STL decomposition + damped trend + promotion lift calibration",
        "backtest_window": window,
    }
