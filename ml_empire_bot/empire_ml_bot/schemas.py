from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Observation:
    castle_name: str
    food: int
    wood: int
    stone: int
    public_order: int
    free_tiles: int
    building_levels: dict[str, int]

    def to_feature_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "castle_name": self.castle_name,
            "food": self.food,
            "wood": self.wood,
            "stone": self.stone,
            "public_order": self.public_order,
            "free_tiles": self.free_tiles,
        }
        for name, level in sorted(self.building_levels.items()):
            payload[f"building_{name}"] = level
        return payload

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StepLog:
    episode_id: str
    step_index: int
    mode: str
    observation: Observation
    action: str
    reward: float
    next_observation: Observation
    done: bool
    info: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "step_index": self.step_index,
            "mode": self.mode,
            "observation": self.observation.to_dict(),
            "action": self.action,
            "reward": self.reward,
            "next_observation": self.next_observation.to_dict(),
            "done": self.done,
            "info": self.info,
        }
