"""Migration: a database created by the pre-weights build gains the columns."""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool


def _old_schema_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        # exactly the old buildings table before weights were configurable
        conn.execute(
            text("CREATE TABLE buildings (id INTEGER PRIMARY KEY, name VARCHAR(80), floors INTEGER)")
        )
        conn.execute(
            text("INSERT INTO buildings (name, floors) VALUES ('旧楼', 12)")
        )
    return engine


def test_adds_weight_columns_with_production_defaults():
    from app.migrate import ensure_building_weight_columns

    engine = _old_schema_engine()
    ensure_building_weight_columns(engine)  # must be idempotent
    ensure_building_weight_columns(engine)

    cols = {c["name"]: c for c in inspect(engine).get_columns("buildings")}
    for name in ("same_dir_bonus", "idle_bonus", "distance_weight"):
        assert name in cols

    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT same_dir_bonus, idle_bonus, distance_weight FROM buildings WHERE name='旧楼'"
        )).one()
    assert row == (40.0, 20.0, 5.0)

    engine.dispose()


def test_noop_when_table_missing():
    from app.migrate import ensure_building_weight_columns

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ensure_building_weight_columns(engine)  # no buildings table yet: should not raise
    engine.dispose()
