from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, JSON,
    ForeignKey, UniqueConstraint, Index,
)
from app.database import Base


class ExternalMarketSignal(Base):
    __tablename__ = "external_market_signals"
    __table_args__ = (
        UniqueConstraint("signal_type", "signal_date", "region", name="uq_ext_signal"),
        Index("ix_ext_signal_date_type", "signal_date", "signal_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    signal_type = Column(String(30), nullable=False)
    signal_date = Column(Date, nullable=False)
    region = Column(String(50))
    category = Column(String(50))
    value = Column(Float, nullable=False)
    raw_value = Column(String(200))
    source = Column(String(50))
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ForecastModelConfig(Base):
    __tablename__ = "forecast_model_configs"
    __table_args__ = (
        UniqueConstraint("store_id", "model_name", name="uq_forecast_model"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    model_name = Column(String(50), nullable=False)
    is_active = Column(Integer, default=1)
    hyperparams = Column(JSON)
    weight_internal = Column(Float, default=0.7)
    weight_external = Column(Float, default=0.3)
    last_tuned_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ForecastAccuracyLog(Base):
    __tablename__ = "forecast_accuracy_logs"
    __table_args__ = (
        Index("ix_forecast_acc_store_date", "store_id", "evaluation_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    model_name = Column(String(50), nullable=False)
    evaluation_date = Column(Date, nullable=False)
    forecast_horizon = Column(Integer, nullable=False)
    mape = Column(Float)
    rmse = Column(Float)
    mae = Column(Float)
    bias = Column(Float)
    sample_size = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ForecastABExperiment(Base):
    __tablename__ = "forecast_ab_experiments"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    experiment_name = Column(String(100), nullable=False)
    model_a = Column(String(50), nullable=False)
    model_b = Column(String(50), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    status = Column(String(20), default="running")
    winner = Column(String(50))
    mape_a = Column(Float)
    mape_b = Column(Float)
    rmse_a = Column(Float)
    rmse_b = Column(Float)
    conclusion = Column(String(500))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
