"""Idempotent lightweight schema migrations.

The project boots with ``Base.metadata.create_all``, which creates missing
tables but never alters existing ones. These helpers add columns introduced
after first release to databases created by an older build, without pulling in
a full migration framework.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.services.dispatch_engine import (
    DISTANCE_WEIGHT,
    IDLE_BONUS,
    SAME_DIR_BONUS,
)

# column name -> (DDL type, production default)
_BUILDING_WEIGHT_COLUMNS: dict[str, tuple[str, float]] = {
    "same_dir_bonus": ("DOUBLE PRECISION", SAME_DIR_BONUS),
    "idle_bonus": ("DOUBLE PRECISION", IDLE_BONUS),
    "distance_weight": ("DOUBLE PRECISION", DISTANCE_WEIGHT),
}


def _column_type(engine: Engine, ddl_type: str) -> str:
    # SQLite understands "DOUBLE" but not "DOUBLE PRECISION" in ADD COLUMN.
    if engine.dialect.name == "sqlite":
        return "FLOAT"
    return ddl_type


def ensure_building_weight_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "buildings" not in inspector.get_table_names():
        return  # create_all builds it with the columns already present
    existing = {col["name"] for col in inspector.get_columns("buildings")}
    with engine.begin() as conn:
        for name, (ddl_type, default) in _BUILDING_WEIGHT_COLUMNS.items():
            if name in existing:
                continue
            col_type = _column_type(engine, ddl_type)
            conn.execute(
                text(
                    f"ALTER TABLE buildings ADD COLUMN {name} {col_type} "
                    f"NOT NULL DEFAULT {default}"
                )
            )
