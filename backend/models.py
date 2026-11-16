from sqlalchemy import Column, Integer, Float, String, Text, Date, JSON, DateTime
from sqlalchemy.sql import func
from database import Base


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    kp_start = Column(Float, nullable=False)
    kp_end = Column(Float, nullable=False)
    points_captured = Column(Integer, default=0)
    crew_count = Column(Integer, default=4)
    weather = Column(String(100), default="")
    # obstacles: list of {name: str, kp: float|null} — old str format auto-migrated on read
    obstacles = Column(JSON, default=[])
    eng_note = Column(Text, default="")
    # GPS coordinates captured in field
    kp_start_lat = Column(Float, nullable=True)
    kp_start_lon = Column(Float, nullable=True)
    kp_end_lat = Column(Float, nullable=True)
    kp_end_lon = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ProjectConfig(Base):
    __tablename__ = "project_config"

    id = Column(Integer, primary_key=True, index=True)
    total_km = Column(Float, default=200.0)
    daily_target_km = Column(Float, default=10.0)
    project_name = Column(String(200), default="Ligne MT 200 km")
    location = Column(String(200), default="")
    start_date = Column(Date, nullable=True)
    engineer_name = Column(String(200), default="")
    logo_path = Column(String(500), default="")
