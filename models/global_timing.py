from sqlalchemy import Column, String, Integer, Boolean
from database import Base


class GlobalTiming(Base):
    __tablename__ = "global_timings"

    id = Column(String, primary_key=True, default="master")

    # THE ADMIN TOGGLE
    manual_peak_override = Column(Boolean, nullable=True)

    # AUTOMATIC TIMINGS
    morning_start = Column(Integer, default=7)
    morning_end = Column(Integer, default=11)

    evening_start = Column(Integer, default=17)
    evening_end = Column(Integer, default=22)

    night_start = Column(Integer, default=23)
    night_end = Column(Integer, default=5)
