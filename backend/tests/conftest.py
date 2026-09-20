"""Test fixtures: in-memory SQLite wired into the app for every test."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def db_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine)

    import app.database as db_mod
    db_mod.engine = engine
    db_mod.SessionLocal = testing_session_local

    # app.main may already be imported from an earlier test; patch its bound
    # globals too so the lifespan uses this test's fresh engine.
    import app.main as main_mod
    main_mod.engine = engine
    main_mod.SessionLocal = testing_session_local

    from app.database import Base
    from app.migrate import ensure_building_weight_columns

    Base.metadata.create_all(bind=engine)
    ensure_building_weight_columns(engine)

    db = testing_session_local()
    from app.services.seed import seed_if_empty
    seed_if_empty(db)
    db.close()

    yield testing_session_local

    engine.dispose()


@pytest.fixture()
def client(db_factory):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c
