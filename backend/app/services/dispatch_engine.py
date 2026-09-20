"""Elevator dispatch: same-direction preference + floor distance; reject if car full.

三项权重（同向加分 / 空闲加分 / 距离权重）按楼栋可配置，
缺省值与现网常数一致；满员判定始终只看容量，与权重无关。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CarState:
    car_id: int
    floor: int
    direction: str  # "up" | "down" | "idle"
    load: int
    capacity: int


@dataclass(frozen=True)
class CallRequest:
    call_id: int
    floor: int
    direction: str  # desired travel after boarding
    passengers: int = 1


@dataclass(frozen=True)
class ScoreResult:
    car_id: int
    score: float
    accepted: bool
    reason: str


# 现网常数：同时作为楼栋权重的缺省值
SAME_DIR_BONUS = 40.0
IDLE_BONUS = 20.0
DISTANCE_WEIGHT = 5.0

# 与现网行为绑定的固定罚分（不在楼栋可配置范围内）
PASSED_PENALTY = 15.0
OPPOSITE_PENALTY = 25.0
FULL_SCORE = -1e9


@dataclass(frozen=True)
class DispatchWeights:
    """一次派工评分使用的权重；缺省即现网常数。"""

    same_dir_bonus: float = SAME_DIR_BONUS
    idle_bonus: float = IDLE_BONUS
    distance_weight: float = DISTANCE_WEIGHT


DEFAULT_WEIGHTS = DispatchWeights()


def weight_summary(weights: DispatchWeights = DEFAULT_WEIGHTS) -> str:
    """回放日志/前端展示用的权重摘要，与评分同源。"""
    return (
        f"权重 同向+{weights.same_dir_bonus:g}"
        f"/空闲+{weights.idle_bonus:g}"
        f"/距离×{weights.distance_weight:g}"
    )


def score_car(
    car: CarState,
    call: CallRequest,
    weights: DispatchWeights = DEFAULT_WEIGHTS,
) -> ScoreResult:
    # 满员判定只按容量，任何权重都不影响
    if car.load + call.passengers > car.capacity:
        return ScoreResult(car.car_id, FULL_SCORE, False, "轿厢满员")

    distance = abs(car.floor - call.floor)
    score = 100.0 - distance * weights.distance_weight

    if car.direction == "idle":
        score += weights.idle_bonus
    elif car.direction == call.direction:
        # approaching or already going same way
        if car.direction == "up" and car.floor <= call.floor:
            score += weights.same_dir_bonus
        elif car.direction == "down" and car.floor >= call.floor:
            score += weights.same_dir_bonus
        else:
            score -= PASSED_PENALTY  # same dir but already passed
    else:
        score -= OPPOSITE_PENALTY

    return ScoreResult(car.car_id, score, True, "ok")


def pick_car(
    cars: list[CarState],
    call: CallRequest,
    weights: DispatchWeights = DEFAULT_WEIGHTS,
) -> ScoreResult | None:
    results = [score_car(c, call, weights) for c in cars]
    accepted = [r for r in results if r.accepted]
    if not accepted:
        return None
    return max(accepted, key=lambda r: r.score)


def congestion_by_floor(calls: list[CallRequest]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for c in calls:
        counts[c.floor] = counts.get(c.floor, 0) + c.passengers
    return counts
