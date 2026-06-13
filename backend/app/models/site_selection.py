from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.database import Base


class CandidateLocation(Base):
    __tablename__ = "candidate_locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    address = Column(String(500))
    latitude = Column(Float)
    longitude = Column(Float)
    city = Column(String(50))
    district = Column(String(100))
    area_sqm = Column(Float)
    monthly_rent = Column(Float)
    submitted_by = Column(Integer, ForeignKey("users.id"))
    status = Column(String(20), default="evaluating")
    created_at = Column(DateTime, server_default=func.now())


class LocationFactor(Base):
    __tablename__ = "location_factors"
    __table_args__ = (
        Index("ix_loc_factor", "location_id", "factor_type"),
    )

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("candidate_locations.id"), nullable=False)
    factor_type = Column(String(30), nullable=False)
    factor_name = Column(String(100), nullable=False)
    raw_value = Column(Float)
    normalized_score = Column(Float)
    data_source = Column(String(100))
    updated_at = Column(DateTime, server_default=func.now())


class SiteEvaluation(Base):
    __tablename__ = "site_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("candidate_locations.id"), nullable=False)
    total_score = Column(Float, default=0)
    traffic_score = Column(Float, default=0)
    competition_score = Column(Float, default=0)
    demographic_score = Column(Float, default=0)
    transport_score = Column(Float, default=0)
    commercial_score = Column(Float, default=0)
    predicted_monthly_revenue = Column(Float)
    predicted_payback_months = Column(Float)
    confidence_level = Column(Float)
    weight_profile_used = Column(Integer, ForeignKey("site_weight_profiles.id"))
    evaluated_at = Column(DateTime, server_default=func.now())
    evaluated_by = Column(Integer, ForeignKey("users.id"))


class SiteWeightProfile(Base):
    __tablename__ = "site_weight_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    traffic_weight = Column(Float, default=0.25)
    competition_weight = Column(Float, default=0.20)
    demographic_weight = Column(Float, default=0.20)
    transport_weight = Column(Float, default=0.15)
    commercial_weight = Column(Float, default=0.20)
    is_default = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id"))


class CompetitorLocation(Base):
    __tablename__ = "competitor_locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    brand = Column(String(100))
    category = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    city = Column(String(50))
    district = Column(String(100))
    estimated_revenue = Column(Float)
    data_source = Column(String(100))
    imported_at = Column(DateTime, server_default=func.now())
