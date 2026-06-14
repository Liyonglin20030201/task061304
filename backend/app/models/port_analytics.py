from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Index
from sqlalchemy.sql import func
from app.database import Base


class YardMetricsHourly(Base):
    __tablename__ = "yard_metrics_hourly"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_time = Column(DateTime, nullable=False)
    total_containers = Column(Integer, default=0)
    throughput_teu = Column(Integer, default=0)
    avg_crane_utilization = Column(Float, default=0)
    avg_agv_utilization = Column(Float, default=0)
    total_energy_kwh = Column(Float, default=0)
    personnel_on_duty = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_yard_metrics_time", "metric_time"),
    )


class ReportTemplate(Base):
    __tablename__ = "port_report_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    template_type = Column(String(50), nullable=False)
    config = Column(JSON)
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
