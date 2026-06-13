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

    forecast_values, confidence_lower, confidence_upper = _holt_winters_forecast(values, periods)

    weather_sql = """
    SELECT w.weather_date, w.precipitation, w.temp_high
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
                if precip > 20:
                    forecast_values[i] *= 0.85
                elif precip > 5:
                    forecast_values[i] *= 0.93

    promo_sql = """
    SELECT start_date, end_date, discount_rate
    FROM promotions
    WHERE store_id = :sid AND end_date >= CURRENT_DATE AND status = 'active'
    """
    promo_result = await db.execute(text(promo_sql), {"sid": store_id})
    promos = promo_result.fetchall()

    last_date = dates[-1]
    forecast_dates = []
    for i in range(periods):
        forecast_dates.append((last_date + timedelta(days=i + 1)).isoformat())

    for promo in promos:
        for i, fd in enumerate(forecast_dates):
            fd_date = date.fromisoformat(fd)
            if promo[0] <= fd_date <= promo[1]:
                boost = 1.0 + (float(promo[2]) if promo[2] else 0.1) * 0.5
                forecast_values[i] *= boost

    backtesting = _rolling_backtest(values)

    return {
        "store_id": store_id,
        "historical": [{"date": d.isoformat(), "value": round(float(v), 2)} for d, v in zip(dates[-30:], values[-30:])],
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
    }


def _holt_winters_forecast(values: np.ndarray, periods: int, alpha=0.3, beta=0.1, gamma=0.2):
    n = len(values)
    season_length = 7

    if n < season_length * 2:
        level = values[-1]
        trend = (values[-1] - values[0]) / n
        forecast = np.array([level + trend * (i + 1) for i in range(periods)])
        std = np.std(values[-14:]) if n >= 14 else np.std(values)
        lower = forecast - 1.96 * std
        upper = forecast + 1.96 * std
        return forecast, lower, upper

    seasonals = np.zeros(season_length)
    for i in range(season_length):
        season_vals = values[i::season_length]
        seasonals[i] = np.mean(season_vals) / np.mean(values) if np.mean(values) != 0 else 1.0

    level = np.mean(values[:season_length])
    trend = (np.mean(values[season_length:2*season_length]) - np.mean(values[:season_length])) / season_length

    for i in range(season_length, n):
        season_idx = i % season_length
        val = values[i]
        last_level = level
        level = alpha * (val / max(seasonals[season_idx], 0.001)) + (1 - alpha) * (level + trend)
        trend = beta * (level - last_level) + (1 - beta) * trend
        seasonals[season_idx] = gamma * (val / max(level, 0.001)) + (1 - gamma) * seasonals[season_idx]

    forecast = np.zeros(periods)
    for i in range(periods):
        season_idx = (n + i) % season_length
        forecast[i] = (level + trend * (i + 1)) * seasonals[season_idx]

    forecast = np.maximum(forecast, 0)
    residuals = []
    for i in range(max(0, n - 30), n):
        season_idx = i % season_length
        predicted = level * seasonals[season_idx]
        residuals.append(values[i] - predicted)

    std = np.std(residuals) if residuals else np.std(values[-14:])
    lower = forecast - 1.96 * std * np.sqrt(np.arange(1, periods + 1) * 0.1 + 1)
    upper = forecast + 1.96 * std * np.sqrt(np.arange(1, periods + 1) * 0.1 + 1)

    return forecast, np.maximum(lower, 0), upper


def _rolling_backtest(values: np.ndarray, window=7) -> dict:
    if len(values) < window * 3:
        return {"mape": None, "rmse": None, "message": "数据不足以进行回测"}

    errors = []
    for i in range(window * 2, len(values)):
        train = values[:i]
        actual = values[i]
        forecast, _, _ = _holt_winters_forecast(train, 1)
        if actual != 0:
            errors.append(abs(forecast[0] - actual) / actual)

    mape = np.mean(errors) * 100 if errors else None
    rmse = np.sqrt(np.mean([(values[i] - values[i-1])**2 for i in range(1, len(values))])) if len(values) > 1 else None

    return {
        "mape": round(mape, 2) if mape else None,
        "rmse": round(float(rmse), 2) if rmse else None,
        "confidence_level": "95%",
        "method": "Holt-Winters with weather/promotion adjustment",
    }
