from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.dispatch_engine import (
    DEFAULT_WEIGHTS,
    DISTANCE_WEIGHT,
    IDLE_BONUS,
    SAME_DIR_BONUS,
    DispatchWeights,
    weight_summary as format_weight_summary,
)


class Building(Base):
    __tablename__ = "buildings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    floors: Mapped[int] = mapped_column(Integer)
    # 派工评分权重，缺省与现网常数一致
    same_dir_bonus: Mapped[float] = mapped_column(Float, default=SAME_DIR_BONUS)
    idle_bonus: Mapped[float] = mapped_column(Float, default=IDLE_BONUS)
    distance_weight: Mapped[float] = mapped_column(Float, default=DISTANCE_WEIGHT)
    cars: Mapped[list["ElevatorCar"]] = relationship(back_populates="building")


class ElevatorCar(Base):
    __tablename__ = "elevator_cars"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"))
    label: Mapped[str] = mapped_column(String(40))
    floor: Mapped[int] = mapped_column(Integer, default=1)
    direction: Mapped[str] = mapped_column(String(10), default="idle")
    load: Mapped[int] = mapped_column(Integer, default=0)
    capacity: Mapped[int] = mapped_column(Integer, default=10)
    building: Mapped[Building] = relationship(back_populates="cars")


class CallTicket(Base):
    __tablename__ = "call_tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"))
    floor: Mapped[int] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(10))
    passengers: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    assigned_car_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DispatchLog(Base):
    __tablename__ = "dispatch_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("call_tickets.id"))
    car_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(String(240))
    # 本次派工实际使用的权重快照，回放时与得分计算同一套数
    same_dir_bonus: Mapped[float | None] = mapped_column(Float, nullable=True)
    idle_bonus: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def weight_summary(self) -> str:
        if self.same_dir_bonus is None:
            return ""
        return format_weight_summary(
            DispatchWeights(
                same_dir_bonus=self.same_dir_bonus,
                idle_bonus=self.idle_bonus if self.idle_bonus is not None else DEFAULT_WEIGHTS.idle_bonus,
                distance_weight=self.distance_weight
                if self.distance_weight is not None
                else DEFAULT_WEIGHTS.distance_weight,
            )
        )


def ensure_schema_columns(engine) -> None:
    """轻量迁移：为存量库补列（项目无 Alembic），缺省值与现网常数一致。"""
    with engine.begin() as conn:
        cols = {
            row[1]
            for row in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'buildings'"
                )
            )
        }
        if cols:
            if "same_dir_bonus" not in cols:
                conn.execute(
                    text(
                        f"ALTER TABLE buildings ADD COLUMN same_dir_bonus DOUBLE PRECISION "
                        f"NOT NULL DEFAULT {SAME_DIR_BONUS}"
                    )
                )
            if "idle_bonus" not in cols:
                conn.execute(
                    text(
                        f"ALTER TABLE buildings ADD COLUMN idle_bonus DOUBLE PRECISION "
                        f"NOT NULL DEFAULT {IDLE_BONUS}"
                    )
                )
            if "distance_weight" not in cols:
                conn.execute(
                    text(
                        f"ALTER TABLE buildings ADD COLUMN distance_weight DOUBLE PRECISION "
                        f"NOT NULL DEFAULT {DISTANCE_WEIGHT}"
                    )
                )
        log_cols = {
            row[1]
            for row in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'dispatch_logs'"
                )
            )
        }
        if log_cols:
            for name in ("same_dir_bonus", "idle_bonus", "distance_weight"):
                if name not in log_cols:
                    conn.execute(
                        text(
                            f"ALTER TABLE dispatch_logs ADD COLUMN {name} DOUBLE PRECISION"
                        )
                    )
