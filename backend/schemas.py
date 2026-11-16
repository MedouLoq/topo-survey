from pydantic import BaseModel, field_validator
from datetime import date
from typing import List, Optional, Any


# ── Obstacle item (new format) ────────────────────────────────────────────
class ObstacleItem(BaseModel):
    name: str
    kp: Optional[float] = None  # KP position where obstacle was found


def normalize_obstacles(raw: Any) -> List[ObstacleItem]:
    """Convert old list-of-strings OR new list-of-dicts to List[ObstacleItem]."""
    if not raw:
        return []
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append(ObstacleItem(name=item, kp=None))
        elif isinstance(item, dict):
            result.append(ObstacleItem(name=item.get("name", ""), kp=item.get("kp")))
        elif isinstance(item, ObstacleItem):
            result.append(item)
    return result


# ── Report schemas ────────────────────────────────────────────────────────
class DailyReportCreate(BaseModel):
    date: date
    kp_start: float
    kp_end: float
    points_captured: int = 0
    crew_count: int = 4
    weather: str = ""
    obstacles: List[ObstacleItem] = []
    eng_note: str = ""
    kp_start_lat: Optional[float] = None
    kp_start_lon: Optional[float] = None
    kp_end_lat: Optional[float] = None
    kp_end_lon: Optional[float] = None

    @field_validator("kp_end")
    @classmethod
    def kp_end_gt_start(cls, v, info):
        if "kp_start" in info.data and v <= info.data["kp_start"]:
            raise ValueError("kp_end doit être supérieur à kp_start")
        return v

    def model_dump_for_db(self):
        d = self.model_dump()
        d["obstacles"] = [o.model_dump() for o in self.obstacles]
        return d


class DailyReportUpdate(BaseModel):
    kp_start: Optional[float] = None
    kp_end: Optional[float] = None
    points_captured: Optional[int] = None
    crew_count: Optional[int] = None
    weather: Optional[str] = None
    obstacles: Optional[List[ObstacleItem]] = None
    eng_note: Optional[str] = None
    kp_start_lat: Optional[float] = None
    kp_start_lon: Optional[float] = None
    kp_end_lat: Optional[float] = None
    kp_end_lon: Optional[float] = None


class DailyReportOut(BaseModel):
    id: int
    date: date
    kp_start: float
    kp_end: float
    km_done: float
    points_captured: int
    crew_count: int
    weather: str
    obstacles: List[ObstacleItem]
    eng_note: str
    kp_start_lat: Optional[float]
    kp_start_lon: Optional[float]
    kp_end_lat: Optional[float]
    kp_end_lon: Optional[float]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_ext(cls, obj):
        return cls(
            id=obj.id,
            date=obj.date,
            kp_start=obj.kp_start,
            kp_end=obj.kp_end,
            km_done=round(obj.kp_end - obj.kp_start, 3),
            points_captured=obj.points_captured,
            crew_count=obj.crew_count,
            weather=obj.weather,
            obstacles=normalize_obstacles(obj.obstacles),
            eng_note=obj.eng_note or "",
            kp_start_lat=obj.kp_start_lat,
            kp_start_lon=obj.kp_start_lon,
            kp_end_lat=obj.kp_end_lat,
            kp_end_lon=obj.kp_end_lon,
        )


# ── Config schemas ────────────────────────────────────────────────────────
class ProjectConfigOut(BaseModel):
    id: int
    total_km: float
    daily_target_km: float
    project_name: str
    location: str
    start_date: Optional[date]
    engineer_name: str
    logo_path: str

    model_config = {"from_attributes": True}


class ProjectConfigUpdate(BaseModel):
    total_km: Optional[float] = None
    daily_target_km: Optional[float] = None
    project_name: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[date] = None
    engineer_name: Optional[str] = None


# ── Stats ─────────────────────────────────────────────────────────────────
class StatsOut(BaseModel):
    total_km: float
    daily_target_km: float
    km_done: float
    km_remaining: float
    pct_done: float
    days_worked: int
    days_remaining_estimated: int
    total_points: int
    total_obstacles: int
    avg_km_per_day: float
