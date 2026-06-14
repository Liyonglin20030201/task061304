from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Index
from sqlalchemy.sql import func
from app.database import Base


class Container(Base):
    __tablename__ = "containers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    container_code = Column(String(20), unique=True, nullable=False)
    container_type = Column(String(10), nullable=False)
    weight_tons = Column(Float)
    owner = Column(String(100))
    vessel_name = Column(String(200))
    voyage_no = Column(String(50))
    bill_of_lading = Column(String(50))
    status = Column(String(20), default="en_route")
    arrival_time = Column(DateTime)
    departure_time = Column(DateTime)
    yard_block = Column(String(10))
    yard_bay = Column(Integer)
    yard_row = Column(Integer)
    yard_tier = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_containers_vessel", "vessel_name", "voyage_no"),
        Index("ix_containers_status", "status"),
    )


class ContainerEvent(Base):
    __tablename__ = "container_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    container_id = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)
    event_time = Column(DateTime, nullable=False)
    location = Column(String(100))
    equipment_id = Column(Integer)
    operator_id = Column(Integer)
    details = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_container_events_container_time", "container_id", "event_time"),
        Index("ix_container_events_type_time", "event_type", "event_time"),
    )
