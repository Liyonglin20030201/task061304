from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.database import Base


class StoreEquipment(Base):
    __tablename__ = "store_equipment"
    __table_args__ = (
        UniqueConstraint("store_id", "equipment_code", name="uq_store_equipment_code"),
        Index("ix_store_equipment_store", "store_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    equipment_code = Column(String(50), nullable=False)
    equipment_type = Column(String(30), nullable=False)  # hvac/lighting/refrigeration/pos/other
    name = Column(String(100), nullable=False)
    brand = Column(String(50), nullable=True)
    model_no = Column(String(50), nullable=True)
    rated_power_kw = Column(Float, nullable=False)
    installed_date = Column(Date, nullable=True)
    zone_id = Column(Integer, ForeignKey("store_zones.id"), nullable=True)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, server_default=func.now())


class StoreEnergyReading(Base):
    __tablename__ = "store_energy_readings"
    __table_args__ = (
        Index("ix_store_energy_equip_time", "equipment_id", "reading_time"),
        Index("ix_store_energy_store_time", "store_id", "reading_time"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    equipment_id = Column(Integer, ForeignKey("store_equipment.id"), nullable=False)
    reading_time = Column(DateTime, nullable=False)
    power_kw = Column(Float, nullable=False)
    energy_kwh = Column(Float, nullable=False)
    temperature_c = Column(Float, nullable=True)
    humidity_pct = Column(Float, nullable=True)


class StoreEnergyDaily(Base):
    __tablename__ = "store_energy_daily"
    __table_args__ = (
        UniqueConstraint("equipment_id", "energy_date", name="uq_store_energy_daily_equip_date"),
        Index("ix_energy_daily_store", "store_id", "energy_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    equipment_id = Column(Integer, ForeignKey("store_equipment.id"), nullable=False)
    energy_date = Column(Date, nullable=False)
    total_kwh = Column(Float, nullable=False)
    peak_kw = Column(Float, nullable=True)
    avg_kw = Column(Float, nullable=True)
    operating_hours = Column(Float, nullable=True)
    cost_yuan = Column(Float, nullable=True)


class StoreEnergyBudget(Base):
    __tablename__ = "store_energy_budget"
    __table_args__ = (
        UniqueConstraint("store_id", "year_month", name="uq_store_energy_budget"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    year_month = Column(String(7), nullable=False)  # e.g. "2026-06"
    budget_kwh = Column(Float, nullable=False)
    budget_yuan = Column(Float, nullable=False)
    alert_threshold_pct = Column(Float, default=80)


class StoreEnergyAlert(Base):
    __tablename__ = "store_energy_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    equipment_id = Column(Integer, ForeignKey("store_equipment.id"), nullable=True)
    alert_type = Column(String(30), nullable=False)  # budget_exceeded/anomaly/peak_warning
    alert_level = Column(String(10), nullable=False)  # info/warning/critical
    message = Column(String(500), nullable=False)
    metric_value = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    alert_time = Column(DateTime, nullable=False)
    is_acknowledged = Column(Integer, default=0)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class EquipmentSchedule(Base):
    __tablename__ = "equipment_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    equipment_id = Column(Integer, ForeignKey("store_equipment.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0-6 (Mon-Sun)
    start_hour = Column(Integer, nullable=False)
    end_hour = Column(Integer, nullable=False)
    power_level = Column(String(20), nullable=False)  # full/reduced/standby/off
    effective_date = Column(Date, nullable=True)
    is_active = Column(Integer, default=1)
