from app.services.dispatch_engine import (
    DEFAULT_WEIGHTS,
    DISTANCE_WEIGHT,
    IDLE_BONUS,
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


# —— 缺省权重必须与现网常数一致 ——

def test_default_weights_match_production_constants():
    assert DEFAULT_WEIGHTS.same_dir_bonus == SAME_DIR_BONUS == 40.0
    assert DEFAULT_WEIGHTS.idle_bonus == IDLE_BONUS == 20.0
    assert DEFAULT_WEIGHTS.distance_weight == DISTANCE_WEIGHT == 5.0


# —— 缺省权重下与现网金样逐分一致（公式：100 - 距离×5，同向+40/空闲+20/过站-15/反向-25）——

def test_golden_score_same_direction_approaching():
    # 2F 上行车接 4F 上行呼梯：100 - 2*5 + 40 = 130
    r = score_car(CarState(1, 2, "up", 1, 10), CallRequest(1, 4, "up"))
    assert r.accepted is True
    assert r.score == 130.0


def test_golden_score_idle():
    # 3F 空闲车接 1F 呼梯：100 - 2*5 + 20 = 110
    r = score_car(CarState(2, 3, "idle", 0, 10), CallRequest(2, 1, "up"))
    assert r.score == 110.0


def test_golden_score_same_direction_already_passed():
    # 8F 上行车（已过站）接 4F 上行呼梯：100 - 4*5 - 15 = 65
    r = score_car(CarState(3, 8, "up", 0, 10), CallRequest(3, 4, "up"))
    assert r.score == 65.0


def test_golden_score_opposite_direction():
    # 12F 下行车接 5F 上行呼梯：100 - 7*5 - 25 = 40
    r = score_car(CarState(4, 12, "down", 0, 10), CallRequest(4, 5, "up"))
    assert r.score == 40.0


def test_golden_pick_matches_legacy_scenarios():
    # 现网既有用例的精确比分
    cars = [
        CarState(1, 2, "up", load=1, capacity=10),
        CarState(2, 12, "idle", load=0, capacity=10),
    ]
    call = CallRequest(9, 4, "up", 1)
    results = {r.car_id: r.score for r in (score_car(c, call) for c in cars)}
    assert results == {1: 130.0, 2: 80.0}
    assert pick_car(cars, call).car_id == 1

    cars2 = [
        CarState(1, 10, "down", load=0, capacity=10),
        CarState(2, 3, "idle", load=0, capacity=10),
    ]
    call2 = CallRequest(3, 2, "up", 1)
    results2 = {r.car_id: r.score for r in (score_car(c, call2) for c in cars2)}
    assert results2 == {1: 35.0, 2: 115.0}
    assert pick_car(cars2, call2).car_id == 2


# —— 同一组轿厢与呼梯：仅调大距离权重即切换胜者 ——

def _switch_fixture():
    # 呼梯 6F 上行；1 号车 3F 上行（同向接近，距离 3）；2 号车 6F 空闲（距离 0）
    cars = [
        CarState(1, 3, "up", load=0, capacity=10),
        CarState(2, 6, "idle", load=0, capacity=10),
    ]
    call = CallRequest(7, 6, "up", 1)
    return cars, call


def test_default_distance_weight_prefers_same_direction_car():
    cars, call = _switch_fixture()
    # 100 - 3*5 + 40 = 125  >  100 - 0 + 20 = 120
    best = pick_car(cars, call, DEFAULT_WEIGHTS)
    assert best is not None and best.car_id == 1


def test_larger_distance_weight_switches_winner():
    cars, call = _switch_fixture()
    heavy = DispatchWeights(distance_weight=10.0)
    # 100 - 3*10 + 40 = 110  <  100 - 0 + 20 = 120，胜者换成空闲近车
    best = pick_car(cars, call, heavy)
    assert best is not None and best.car_id == 2


def test_winner_switch_is_caused_only_by_distance_weight():
    cars, call = _switch_fixture()
    # 交点：140-3w = 120 -> w = 20/3 ≈ 6.67
    assert pick_car(cars, call, DispatchWeights(distance_weight=5.0)).car_id == 1
    assert pick_car(cars, call, DispatchWeights(distance_weight=6.5)).car_id == 1
    assert pick_car(cars, call, DispatchWeights(distance_weight=7.0)).car_id == 2
    assert pick_car(cars, call, DispatchWeights(distance_weight=10.0)).car_id == 2


# —— 满员判定始终按容量，权重再大都不影响 ——

def test_full_car_rejected_even_with_extreme_distance_weight():
    cars = [
        CarState(1, 5, "idle", load=10, capacity=10),   # 就在呼梯楼层但满员
        CarState(2, 1, "idle", load=0, capacity=10),    # 4 层外的可用车
    ]
    call = CallRequest(8, 5, "up", 1)
    heavy = DispatchWeights(distance_weight=1000.0)
    scored = [score_car(c, call, heavy) for c in cars]
    assert scored[0].accepted is False
    assert scored[1].accepted is True
    best = pick_car(cars, call, heavy)
    assert best is not None and best.car_id == 2


def test_all_full_returns_none_regardless_of_weights():
    cars = [CarState(1, 5, "idle", load=8, capacity=8)]
    call = CallRequest(9, 5, "up", 1)
    assert pick_car(cars, call, DispatchWeights(distance_weight=0.0)) is None


def test_weight_summary_uses_same_numbers_as_scoring():
    assert weight_summary() == "权重 同向+40/空闲+20/距离×5"
    heavy = DispatchWeights(distance_weight=10.0)
    assert "距离×10" in weight_summary(heavy)
