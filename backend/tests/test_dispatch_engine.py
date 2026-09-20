import pytest

from app.services.dispatch_engine import (
    DEFAULT_WEIGHTS,
    DISTANCE_WEIGHT,
    IDLE_BONUS,
    REJECT_SCORE,
    SAME_DIR_BONUS,
    CallRequest,
    CarState,
    DispatchWeights,
    pick_car,
    score_car,
    weight_summary,
)


def test_reject_when_full():
    car = CarState(1, 5, "idle", load=8, capacity=8)
    call = CallRequest(1, 5, "up", passengers=1)
    r = score_car(car, call)
    assert r.accepted is False
    assert "满员" in r.reason


def test_same_direction_beats_far_idle():
    cars = [
        CarState(1, 2, "up", load=1, capacity=10),
        CarState(2, 12, "idle", load=0, capacity=10),
    ]
    call = CallRequest(9, 4, "up", 1)
    best = pick_car(cars, call)
    assert best is not None
    assert best.car_id == 1


def test_closer_idle_wins_when_opposite():
    cars = [
        CarState(1, 10, "down", load=0, capacity=10),
        CarState(2, 3, "idle", load=0, capacity=10),
    ]
    call = CallRequest(3, 2, "up", 1)
    best = pick_car(cars, call)
    assert best is not None
    assert best.car_id == 2


# —— golden baseline: DEFAULT_WEIGHTS must reproduce the production constants ——

def test_default_weights_are_production_constants():
    assert SAME_DIR_BONUS == 40.0
    assert IDLE_BONUS == 20.0
    assert DISTANCE_WEIGHT == 5.0
    assert DEFAULT_WEIGHTS == DispatchWeights(40.0, 20.0, 5.0)


@pytest.mark.parametrize(
    "car, call, expected",
    [
        # idle at the call floor: 100 + 20 idle bonus
        (CarState(1, 5, "idle", 0, 10), CallRequest(1, 5, "up"), 120.0),
        # idle 6 floors away: 100 - 6*5 + 20
        (CarState(2, 11, "idle", 0, 10), CallRequest(2, 5, "up"), 90.0),
        # up, same direction, still approaching, 3 floors away: 100 - 15 + 40
        (CarState(3, 2, "up", 0, 10), CallRequest(3, 5, "up"), 125.0),
        # down, same direction, still above call, 4 floors away: 100 - 20 + 40
        (CarState(4, 14, "down", 0, 10), CallRequest(4, 10, "down"), 120.0),
        # up but already passed the call, 4 floors away: 100 - 20 - 15
        (CarState(5, 9, "up", 0, 10), CallRequest(5, 5, "up"), 65.0),
        # opposite direction, 6 floors away: 100 - 30 - 25
        (CarState(6, 2, "down", 0, 10), CallRequest(6, 8, "up"), 45.0),
    ],
)
def test_default_weights_golden_scores(car, call, expected):
    r = score_car(car, call)  # default weights
    assert r.accepted is True
    assert r.score == expected


# —— winner switches when the distance weight is raised ——

def _switch_cars():
    # A: same direction but 4 floors away; B: idle and only 1 floor away.
    return [
        CarState(1, 6, "up", load=0, capacity=10),
        CarState(2, 11, "idle", load=0, capacity=10),
    ]


_SWITCH_CALL = CallRequest(7, 10, "up", 1)


def test_default_distance_weight_prefers_same_direction_car():
    best = pick_car(_switch_cars(), _SWITCH_CALL)  # w = 5
    assert best is not None and best.car_id == 1  # A: 120 vs B: 115


def test_raising_distance_weight_flips_winner():
    heavy = DispatchWeights(distance_weight=10.0)  # bonuses stay at defaults
    best = pick_car(_switch_cars(), _SWITCH_CALL, heavy)
    assert best is not None and best.car_id == 2  # B: 110 vs A: 100


def test_distance_weight_switch_boundary():
    # threshold: same-dir lead (40-20) / distance gap (4-1) = 6.666...
    below = pick_car(_switch_cars(), _SWITCH_CALL, DispatchWeights(distance_weight=6.0))
    above = pick_car(_switch_cars(), _SWITCH_CALL, DispatchWeights(distance_weight=8.0))
    assert below.car_id == 1
    assert above.car_id == 2


# —— fullness is capacity-based and must never depend on weights ——

@pytest.mark.parametrize("w", [0.0, 5.0, 999.0])
def test_full_car_rejected_regardless_of_weights(w):
    car = CarState(1, 10, "idle", load=10, capacity=10)
    call = CallRequest(1, 1, "up", passengers=1)
    r = score_car(car, call, DispatchWeights(distance_weight=w))
    assert r.accepted is False
    assert r.score == REJECT_SCORE


def test_pick_car_none_when_all_full_even_with_extreme_weights():
    cars = [
        CarState(1, 10, "idle", load=10, capacity=10),
        CarState(2, 1, "up", load=9, capacity=10),
    ]
    call = CallRequest(1, 5, "up", passengers=2)
    assert pick_car(cars, call, DispatchWeights(distance_weight=1000.0)) is None


def test_weight_summary_matches_weights_used():
    w = DispatchWeights(same_dir_bonus=40, idle_bonus=20, distance_weight=10)
    assert weight_summary(w) == "权重 同向40/空闲20/距离10"
    assert weight_summary() == "权重 同向40/空闲20/距离5"
