from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Index
from sqlalchemy.sql import func
from app.database import Base


class PortEquipment(Base):
    __tablename__ = "port_equipment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_code = Column(String(50), unique=True, nullable=False)
    equipment_type = Column(String(20), nullable=False)
    name = Column(String(200), nullable=False)
    max_power_kw = Column(Float, nullable=False)
    location_x = Column(Float, default=0)
    location_y = Column(Float, default=0)
    location_z = Column(Float, default=0)
    status = Column(String(20), default="idle")
    created_at = Column(DateTime, server_default=func.now())


class EnergyReading(Base):
    __tablename__ = "energy_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    power_kw = Column(Float, nullable=False)
    energy_kwh = Column(Float, nullable=False)
    voltage = Column(Float)
    current_amps = Column(Float)
    operational_state = Column(String(20))

    __table_args__ = (
        Index("ix_energy_readings_equip_time", "equipment_id", "timestamp"),
    )


class EnergyCostConfig(Base):
    __tablename__ = "energy_cost_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    period_name = Column(String(50), nullable=False)
    start_hour = Column(Integer, nullable=False)
    end_hour = Column(Integer, nullable=False)
    rate_per_kwh = Column(Float, nullable=False)
    effective_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
