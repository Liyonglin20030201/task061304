from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, Index
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        Index("ix_members_phone", "phone"),
    )

    id = Column(Integer, primary_key=True, index=True)
    member_no = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(50))
    phone = Column(String(20))
    gender = Column(String(10))
    birthday = Column(Date)
    register_date = Column(Date, nullable=False)
    register_store_id = Column(Integer, ForeignKey("stores.id"))
    level = Column(String(20), default="normal")
    total_points = Column(Integer, default=0)
    tags = Column(ARRAY(String), default=[])
    rfm_segment = Column(String(30))
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    sales = relationship("Sale", back_populates="member")
    transactions = relationship("MemberTransaction", back_populates="member")


class MemberTransaction(Base):
    __tablename__ = "member_transactions"
    __table_args__ = (
        Index("ix_member_tx_member_date", "member_id", "transaction_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Float, nullable=False)
    points_earned = Column(Integer, default=0)
    points_used = Column(Integer, default=0)
    receipt_no = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    member = relationship("Member", back_populates="transactions")
