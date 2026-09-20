"""Elevator dispatch: same-direction preference + floor distance; reject if car full.

The three scoring knobs (same-direction bonus, idle bonus, distance weight)
are per-building configurable via ``DispatchWeights``. The defaults below are
exactly the constants the production engine used historically, so a building
without an explicit configuration scores identically to the old golden logic.
"""

from __future__ import annotations

from dataclasses import dataclass


# —— production defaults; changing these changes the golden baseline, do not touch ——
SAME_DIR_BONUS = 40.0
IDLE_BONUS = 20.0
DISTANCE_WEIGHT = 5.0

# fixed adjustments that are not building-configurable
BASE_SCORE = 100.0
PASSED_PENALTY = 15.0
OPPOSITE_PENALTY = 25.0
REJECT_SCORE = -1e9


@dataclass(frozen=True)
class DispatchWeights:
    """Scoring weights for one building. Defaults match the production constants."""

    same_dir_bonus: float = SAME_DIR_BONUS
    idle_bonus: float = IDLE_BONUS
    distance_weight: float = DISTANCE_WEIGHT


DEFAULT_WEIGHTS = DispatchWeights()


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


def score_car(
    car: CarState,
    call: CallRequest,
    weights: DispatchWeights = DEFAULT_WEIGHTS,
) -> ScoreResult:
    # Fullness is decided by capacity alone; weights never affect it.
    if car.load + call.passengers > car.capacity:
        return ScoreResult(car.car_id, REJECT_SCORE, False, "轿厢满员")

    distance = abs(car.floor - call.floor)
    score = BASE_SCORE - distance * weights.distance_weight

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


def weight_summary(weights: DispatchWeights = DEFAULT_WEIGHTS) -> str:
    """One-line summary embedded in dispatch logs/replays.

    Rendered from the very ``DispatchWeights`` instance passed to
    ``score_car``/``pick_car`` for the same dispatch, so the replay can never
    quote weights other than the ones actually used.
    """

    return (
        f"权重 同向{weights.same_dir_bonus:g}/空闲{weights.idle_bonus:g}"
        f"/距离{weights.distance_weight:g}"
    )


def congestion_by_floor(calls: list[CallRequest]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for c in calls:
        counts[c.floor] = counts.get(c.floor, 0) + c.passengers
    return counts
