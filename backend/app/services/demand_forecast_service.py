from datetime import date, datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import numpy as np


async def _get_model_config(db: AsyncSession, store_id: int) -> dict:
    sql = text("""
        SELECT weight_internal, weight_external, hyperparams
        FROM forecast_model_configs
        WHERE store_id = :store_id AND model_name = 'ensemble' AND is_active = 1
    """)
    result = await db.execute(sql, {"store_id": store_id})
    row = result.fetchone()
    if row:
        return {"weight_internal": row[0], "weight_external": row[1], "hyperparams": row[2]}
    return {"weight_internal": 0.7, "weight_external": 0.3, "hyperparams": None}


async def _get_external_signals(db: AsyncSession, store_id: int, start_date: date, end_date: date, category: Optional[str] = None) -> List[dict]:
    cat_filter = ""
    params = {"start": str(start_date), "end": str(end_date)}
    if category:
        cat_filter = "AND (category = :category OR category IS NULL)"
        params["category"] = category

    sql = text(f"""
        SELECT signal_type, signal_date, value, confidence
        FROM external_market_signals
        WHERE signal_date BETWEEN :start AND :end {cat_filter}
        ORDER BY signal_date, signal_type
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()
    return [{"signal_type": r[0], "signal_date": r[1], "value": r[2], "confidence": r[3]} for r in rows]


def _compute_external_factor(signals: List[dict], target_date: date) -> float:
    day_signals = [s for s in signals if s["signal_date"] == target_date or (isinstance(s["signal_date"], str) and s["signal_date"] == str(target_date))]
    if not day_signals:
        return 1.0

    factor = 1.0
    for sig in day_signals:
        conf = sig.get("confidence", 1.0)
        val = sig["value"]
        sig_type = sig["signal_type"]

        if sig_type == "competitor_price":
            if val > 1.1:
                factor *= 1.0 + min(0.10, (val - 1.0) * 0.1) * conf
            elif val < 0.9:
                factor *= 1.0 - min(0.10, (1.0 - val) * 0.1) * conf
        elif sig_type == "market_trend":
            factor *= 1.0 + (val - 1.0) * 0.3 * conf
        elif sig_type == "sentiment":
            factor *= 1.0 + val * 0.08 * conf

    return max(0.5, min(1.5, factor))


async def _get_baseline_forecast(db: AsyncSession, store_id: int, periods: int) -> List[dict]:
    sql = text("""
        SELECT sale_date, SUM(total_amount) as daily_revenue
        FROM sales
        WHERE store_id = :store_id AND sale_date >= CURRENT_DATE - 90
        GROUP BY sale_date ORDER BY sale_date
    """)
    result = await db.execute(sql, {"store_id": store_id})
    rows = result.fetchall()

    if not rows:
        today = date.today()
        return [{"date": str(today + timedelta(days=i)), "forecast": 0, "lower": 0, "upper": 0} for i in range(periods)]

    revenues = np.array([r[1] for r in rows], dtype=float)
    mean_rev = float(np.mean(revenues[-30:])) if len(revenues) >= 30 else float(np.mean(revenues))
    std_rev = float(np.std(revenues[-30:])) if len(revenues) >= 30 else float(np.std(revenues))

    if len(revenues) >= 14:
        trend = float(np.mean(revenues[-7:]) - np.mean(revenues[-14:-7]))
    else:
        trend = 0

    today = date.today()
    forecasts = []
    for i in range(periods):
        fc = mean_rev + trend * (i + 1) * 0.1
        fc = max(0, fc)
        margin = 1.96 * std_rev * np.sqrt(1 + i * 0.05)
        forecasts.append({
            "date": str(today + timedelta(days=i + 1)),
            "forecast": round(fc, 2),
            "lower": round(max(0, fc - margin), 2),
            "upper": round(fc + margin, 2),
        })

    return forecasts


async def get_enhanced_forecast(db: AsyncSession, store_id: int, periods: int = 30, category: Optional[str] = None) -> dict:
    config = await _get_model_config(db, store_id)
    baseline = await _get_baseline_forecast(db, store_id, periods)

    today = date.today()
    end_date = today + timedelta(days=periods)
    signals = await _get_external_signals(db, store_id, today, end_date, category)

    enhanced = []
    signals_used = set()
    for fc in baseline:
        fc_date = date.fromisoformat(fc["date"])
        ext_factor = _compute_external_factor(signals, fc_date)

        if ext_factor != 1.0:
            for s in signals:
                signals_used.add(s["signal_type"])

        w_int = config["weight_internal"]
        w_ext = config["weight_external"]
        base_val = fc["forecast"]
        enhanced_val = w_int * base_val + w_ext * (base_val * ext_factor)

        ci_widening = 1.0 + 0.15 * w_ext
        margin = (fc["upper"] - fc["forecast"]) * ci_widening
        enhanced.append({
            "date": fc["date"],
            "forecast": round(enhanced_val, 2),
            "lower": round(max(0, enhanced_val - margin), 2),
            "upper": round(enhanced_val + margin, 2),
            "external_factor": round(ext_factor, 4),
        })

    return {
        "store_id": store_id,
        "periods": periods,
        "config": config,
        "forecast": enhanced,
        "signals_used": list(signals_used),
    }


async def get_forecast_comparison(db: AsyncSession, store_id: int, periods: int = 30, category: Optional[str] = None) -> dict:
    baseline = await _get_baseline_forecast(db, store_id, periods)
    enhanced_result = await get_enhanced_forecast(db, store_id, periods, category)

    return {
        "store_id": store_id,
        "baseline": baseline,
        "enhanced": enhanced_result["forecast"],
        "improvement_mape": None,
        "external_signals_used": enhanced_result["signals_used"],
    }


async def get_accuracy_history(db: AsyncSession, store_ids: Optional[List[int]], model_name: Optional[str] = None, days: int = 90) -> List[dict]:
    conditions = ["evaluation_date >= CURRENT_DATE - :days"]
    params = {"days": days}
    if store_ids is not None:
        conditions.append("store_id = ANY(:store_ids)")
        params["store_ids"] = store_ids
    if model_name:
        conditions.append("model_name = :model_name")
        params["model_name"] = model_name

    where = " AND ".join(conditions)
    sql = text(f"""
        SELECT model_name, evaluation_date, mape, rmse, mae, bias
        FROM forecast_accuracy_logs
        WHERE {where}
        ORDER BY evaluation_date DESC
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()
    return [{"model_name": r[0], "evaluation_date": str(r[1]), "mape": r[2], "rmse": r[3], "mae": r[4], "bias": r[5]} for r in rows]


async def get_signals(db: AsyncSession, region: Optional[str] = None, signal_type: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[dict]:
    conditions = ["1=1"]
    params = {}
    if region:
        conditions.append("region = :region")
        params["region"] = region
    if signal_type:
        conditions.append("signal_type = :signal_type")
        params["signal_type"] = signal_type
    if start_date:
        conditions.append("signal_date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("signal_date <= :end_date")
        params["end_date"] = end_date

    where = " AND ".join(conditions)
    sql = text(f"""
        SELECT id, signal_type, signal_date, region, category, value, raw_value, source, confidence
        FROM external_market_signals WHERE {where}
        ORDER BY signal_date DESC LIMIT 100
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()
    return [{"id": r[0], "signal_type": r[1], "signal_date": str(r[2]), "region": r[3], "category": r[4], "value": r[5], "raw_value": r[6], "source": r[7], "confidence": r[8]} for r in rows]


async def create_signal(db: AsyncSession, signal_data: dict) -> dict:
    now = datetime.now(timezone.utc)
    insert_data = {
        "signal_type": signal_data["signal_type"],
        "signal_date": signal_data["signal_date"],
        "region": signal_data.get("region"),
        "category": signal_data.get("category"),
        "value": signal_data["value"],
        "raw_value": signal_data.get("raw_value"),
        "source": signal_data.get("source"),
        "confidence": signal_data.get("confidence", 1.0),
        "now": now,
    }
    sql = text("""
        INSERT INTO external_market_signals (signal_type, signal_date, region, category, value, raw_value, source, confidence, created_at)
        VALUES (:signal_type, :signal_date, :region, :category, :value, :raw_value, :source, :confidence, :now)
        ON CONFLICT (signal_type, signal_date, region) DO UPDATE SET value = :value, raw_value = :raw_value, confidence = :confidence
        RETURNING id
    """)
    result = await db.execute(sql, insert_data)
    signal_id = result.scalar()
    await db.commit()
    return {"id": signal_id, "message": "信号已录入"}


async def get_ab_experiments(db: AsyncSession, store_ids: Optional[List[int]], status: Optional[str] = None) -> List[dict]:
    conditions = ["1=1"]
    params = {}
    if store_ids is not None:
        conditions.append("store_id = ANY(:store_ids)")
        params["store_ids"] = store_ids
    if status:
        conditions.append("status = :status")
        params["status"] = status

    where = " AND ".join(conditions)
    sql = text(f"""
        SELECT id, store_id, experiment_name, model_a, model_b, start_date, end_date, status, winner, mape_a, mape_b, conclusion
        FROM forecast_ab_experiments WHERE {where}
        ORDER BY created_at DESC
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()
    return [
        {"id": r[0], "store_id": r[1], "experiment_name": r[2], "model_a": r[3], "model_b": r[4],
         "start_date": str(r[5]), "end_date": str(r[6]) if r[6] else None, "status": r[7],
         "winner": r[8], "mape_a": r[9], "mape_b": r[10], "conclusion": r[11]}
        for r in rows
    ]


async def create_ab_experiment(db: AsyncSession, experiment_data: dict) -> dict:
    now = datetime.now(timezone.utc)
    sql = text("""
        INSERT INTO forecast_ab_experiments (store_id, experiment_name, model_a, model_b, start_date, end_date, status, created_at)
        VALUES (:store_id, :experiment_name, :model_a, :model_b, :start_date, :end_date, 'running', :now)
        RETURNING id
    """)
    result = await db.execute(sql, {**experiment_data, "now": now})
    exp_id = result.scalar()
    await db.commit()
    return {"id": exp_id, "message": "实验已创建"}


async def get_ab_experiment_detail(db: AsyncSession, experiment_id: int) -> dict:
    sql = text("SELECT * FROM forecast_ab_experiments WHERE id = :id")
    result = await db.execute(sql, {"id": experiment_id})
    row = result.fetchone()
    if not row:
        return None
    columns = result.keys()
    return dict(zip(columns, row))


async def auto_tune_model(db: AsyncSession, store_id: int) -> dict:
    config = await _get_model_config(db, store_id)
    today = date.today()
    test_start = today - timedelta(days=30)

    actual_sql = text("""
        SELECT sale_date, SUM(total_amount) as daily_revenue
        FROM sales WHERE store_id = :store_id AND sale_date BETWEEN :start AND :end
        GROUP BY sale_date ORDER BY sale_date
    """)
    actual_result = await db.execute(actual_sql, {"store_id": store_id, "start": str(test_start), "end": str(today)})
    actuals = actual_result.fetchall()

    if len(actuals) < 14:
        return {"message": "历史数据不足，无法调优", "tuned": False}

    actual_values = np.array([r[1] for r in actuals], dtype=float)
    baseline_mean = float(np.mean(actual_values))
    baseline_errors = np.abs(actual_values - baseline_mean)
    baseline_mape = float(np.mean(baseline_errors / np.maximum(actual_values, 1))) * 100

    signals = await _get_external_signals(db, store_id, test_start, today)
    enhanced_errors = []
    for i, act_row in enumerate(actuals):
        act_date = act_row[0]
        ext_factor = _compute_external_factor(signals, act_date)
        enhanced_pred = config["weight_internal"] * baseline_mean + config["weight_external"] * baseline_mean * ext_factor
        enhanced_errors.append(abs(actual_values[i] - enhanced_pred))

    enhanced_mape = float(np.mean(np.array(enhanced_errors) / np.maximum(actual_values, 1))) * 100

    new_w_ext = config["weight_external"]
    if enhanced_mape < baseline_mape - 2:
        new_w_ext = min(0.5, config["weight_external"] + 0.05)
    elif enhanced_mape > baseline_mape:
        new_w_ext = max(0.1, config["weight_external"] - 0.05)

    now = datetime.now(timezone.utc)
    if new_w_ext != config["weight_external"]:
        update_sql = text("""
            INSERT INTO forecast_model_configs (store_id, model_name, is_active, weight_internal, weight_external, last_tuned_at, created_at)
            VALUES (:store_id, 'ensemble', 1, :w_int, :w_ext, :now, :now)
            ON CONFLICT (store_id, model_name) DO UPDATE SET weight_internal = :w_int, weight_external = :w_ext, last_tuned_at = :now
        """)
        await db.execute(update_sql, {"store_id": store_id, "w_int": 1 - new_w_ext, "w_ext": new_w_ext, "now": now})

    log_sql = text("""
        INSERT INTO forecast_accuracy_logs (store_id, model_name, evaluation_date, forecast_horizon, mape, rmse, sample_size, created_at)
        VALUES (:store_id, 'baseline', :eval_date, 30, :mape_b, 0, :sample, :now),
               (:store_id, 'enhanced', :eval_date, 30, :mape_e, 0, :sample, :now)
    """)
    await db.execute(log_sql, {
        "store_id": store_id, "eval_date": today,
        "mape_b": round(baseline_mape, 2), "mape_e": round(enhanced_mape, 2),
        "sample": len(actuals), "now": now,
    })
    await db.commit()

    return {
        "tuned": True,
        "baseline_mape": round(baseline_mape, 2),
        "enhanced_mape": round(enhanced_mape, 2),
        "weight_external_before": config["weight_external"],
        "weight_external_after": new_w_ext,
    }


async def get_model_config(db: AsyncSession, store_id: int) -> dict:
    sql = text("SELECT * FROM forecast_model_configs WHERE store_id = :store_id AND is_active = 1")
    result = await db.execute(sql, {"store_id": store_id})
    rows = result.fetchall()
    if not rows:
        return {"store_id": store_id, "model_name": "ensemble", "weight_internal": 0.7, "weight_external": 0.3}
    columns = result.keys()
    return [dict(zip(columns, r)) for r in rows]


async def update_model_config(db: AsyncSession, config: dict) -> dict:
    now = datetime.now(timezone.utc)
    sql = text("""
        INSERT INTO forecast_model_configs (store_id, model_name, is_active, weight_internal, weight_external, hyperparams, last_tuned_at, created_at)
        VALUES (:store_id, :model_name, 1, :weight_internal, :weight_external, :hyperparams, :now, :now)
        ON CONFLICT (store_id, model_name) DO UPDATE SET weight_internal = :weight_internal, weight_external = :weight_external, hyperparams = :hyperparams, last_tuned_at = :now
    """)
    await db.execute(sql, {
        "store_id": config["store_id"], "model_name": config.get("model_name", "ensemble"),
        "weight_internal": config.get("weight_internal", 0.7), "weight_external": config.get("weight_external", 0.3),
        "hyperparams": str(config.get("hyperparams")) if config.get("hyperparams") else None, "now": now,
    })
    await db.commit()
    return {"message": "模型配置已更新"}
