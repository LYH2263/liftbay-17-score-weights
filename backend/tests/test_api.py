"""End-to-end API tests on seeded SQLite data.

Golden numbers here are hand-computed from the production scoring formula
(100 - distance*5, +40 same-direction approaching, +20 idle, -15 passed,
-25 opposite). The per-building default weights are 40/20/5, so these must
match the current production behaviour exactly.
"""

from app.models.models import Building, ElevatorCar


def _waiting_call(client, floor, direction):
    rows = client.get("/api/calls").json()
    return next(
        c for c in rows
        if c["floor"] == floor and c["direction"] == direction and c["status"] == "waiting"
    )


def test_buildings_expose_production_default_weights(client):
    bs = client.get("/api/buildings").json()
    assert len(bs) == 1
    b = bs[0]
    assert b["same_dir_bonus"] == 40.0
    assert b["idle_bonus"] == 20.0
    assert b["distance_weight"] == 5.0


def test_dispatch_golden_default_weights(client):
    # c1: 5F up, 2 passengers -> A1 (3F up), score 130.0
    c1 = _waiting_call(client, 5, "up")
    r1 = client.post("/api/dispatch", json={"call_id": c1["id"]})
    assert r1.status_code == 200, r1.text
    out1 = r1.json()
    assert out1["assigned_car_id"] == 1
    assert out1["score"] == "130.0"

    # c2: 14F down, 1 passenger -> A2 (12F down, already passed), score 75.0
    c2 = _waiting_call(client, 14, "down")
    r2 = client.post("/api/dispatch", json={"call_id": c2["id"]})
    assert r2.status_code == 200, r2.text
    out2 = r2.json()
    assert out2["assigned_car_id"] == 2
    assert out2["score"] == "75.0"

    # Replay carries the exact weights that produced the scores.
    logs = client.get("/api/replay").json()
    dispatch_logs = [l for l in logs if l["call_id"] in (c1["id"], c2["id"])]
    assert len(dispatch_logs) == 2
    for l in dispatch_logs:
        assert "权重 同向40/空闲20/距离5" in l["detail"]


def test_dispatch_rejects_when_all_full_and_weights_do_not_change_fullness(
    client, db_factory
):
    created = client.post(
        "/api/calls", json={"building_id": 1, "floor": 1, "direction": "up", "passengers": 1}
    ).json()

    # Fill every car to capacity through the DB (capacity-based, weight-proof).
    db = db_factory()
    for car in db.query(ElevatorCar).all():
        car.load = car.capacity
    db.commit()
    db.close()

    # Even a zero distance weight cannot rescue a full car.
    client.patch(
        "/api/buildings/1",
        json={"same_dir_bonus": 40, "idle_bonus": 20, "distance_weight": 0},
    )
    r = client.post("/api/dispatch", json={"call_id": created["id"]})
    assert r.status_code == 409
    ticket = client.get("/api/calls").json()
    assert next(t for t in ticket if t["id"] == created["id"])["status"] == "rejected"
    latest = client.get("/api/replay").json()[0]
    assert latest["car_id"] is None
    assert "满员" in latest["detail"]
    assert "权重 同向40/空闲20/距离0" in latest["detail"]


def test_raising_distance_weight_switches_winner_and_persists(client, db_factory):
    # Fresh building: A is same-direction but 4 floors away (6F up),
    # B is idle and 1 floor away (11F); call at 10F up.
    db = db_factory()
    b = Building(name="权重切换试验楼", floors=18)
    db.add(b)
    db.flush()
    car_a = ElevatorCar(building_id=b.id, label="B1", floor=6, direction="up", load=0, capacity=10)
    car_b = ElevatorCar(building_id=b.id, label="B2", floor=11, direction="idle", load=0, capacity=10)
    db.add_all([car_a, car_b])
    db.commit()
    bid, aid, bid_car = b.id, car_a.id, car_b.id
    db.close()

    call = client.post(
        "/api/calls", json={"building_id": bid, "floor": 10, "direction": "up", "passengers": 1}
    ).json()
    # default weights: A = 120 vs B = 115 -> same-direction A wins
    first = client.post("/api/dispatch", json={"call_id": call["id"]}).json()
    assert first["assigned_car_id"] == aid
    assert first["score"] == "120.0"

    # Same cars/call shape, only the distance weight changes: 5 -> 10.
    r = client.patch(
        f"/api/buildings/{bid}",
        json={"same_dir_bonus": 40, "idle_bonus": 20, "distance_weight": 10},
    )
    assert r.status_code == 200, r.text

    # Re-entering the buildings page ("再次进入") shows the saved values.
    saved = next(x for x in client.get("/api/buildings").json() if x["id"] == bid)
    assert saved["distance_weight"] == 10.0
    assert saved["same_dir_bonus"] == 40.0
    assert saved["idle_bonus"] == 20.0

    # The first dispatch moved/loaded car A; reset both cars to the same
    # starting configuration so the ONLY change is the distance weight.
    db = db_factory()
    ca = db.get(ElevatorCar, aid)
    cb = db.get(ElevatorCar, bid_car)
    ca.floor, ca.direction, ca.load = 6, "up", 0
    cb.floor, cb.direction, cb.load = 11, "idle", 0
    db.commit()
    db.close()

    call2 = client.post(
        "/api/calls", json={"building_id": bid, "floor": 10, "direction": "up", "passengers": 1}
    ).json()
    # w=10: A = 100 vs B = 110 -> the closer idle car B now wins
    second = client.post("/api/dispatch", json={"call_id": call2["id"]}).json()
    assert second["assigned_car_id"] == bid_car
    assert second["score"] == "110.0"

    latest = client.get("/api/replay").json()[0]
    assert "权重 同向40/空闲20/距离10" in latest["detail"]


def test_patch_validates_weights(client):
    ok = client.patch(
        "/api/buildings/1",
        json={"same_dir_bonus": 0, "idle_bonus": 0, "distance_weight": 5.5},
    )
    assert ok.status_code == 200
    assert ok.json()["distance_weight"] == 5.5

    bad = client.patch(
        "/api/buildings/1",
        json={"same_dir_bonus": -1, "idle_bonus": 20, "distance_weight": 5},
    )
    assert bad.status_code == 422

    assert client.patch(
        "/api/buildings/999",
        json={"same_dir_bonus": 1, "idle_bonus": 1, "distance_weight": 1},
    ).status_code == 404
