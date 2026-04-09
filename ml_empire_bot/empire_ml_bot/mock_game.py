from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .adapters import BaseGameAdapter
from .schemas import Observation

RESOURCE_BUILDINGS = ("farm", "lumberyard", "quarry")
ALL_BUILDINGS = RESOURCE_BUILDINGS + ("house", "barracks", "academy")


@dataclass(slots=True)
class CastleState:
    castle_name: str = "Основной замок"
    food: int = 120
    wood: int = 120
    stone: int = 120
    public_order: int = 100
    free_tiles: int = 24
    soldiers: int = 0
    building_levels: dict[str, int] = field(
        default_factory=lambda: {name: 0 for name in ALL_BUILDINGS}
    )


class MockEmpireAdapter(BaseGameAdapter):
    def __init__(self, seed: int | None = 7, max_steps: int = 60):
        self.random = random.Random(seed)
        self.max_steps = max_steps
        self.step_counter = 0
        self.state = CastleState()

    def reset(self) -> Observation:
        self.step_counter = 0
        self.state = CastleState()
        return self._observation()

    def available_actions(self) -> list[str]:
        return [
            "collect_food",
            "collect_wood",
            "collect_stone",
            "upgrade_farm",
            "upgrade_lumberyard",
            "upgrade_quarry",
            "build_house",
            "upgrade_academy",
            "train_soldiers",
            "wait",
        ]

    def expert_action(self, observation: Observation) -> str:
        levels = observation.building_levels
        if observation.food < 80:
            return "collect_food"
        if observation.wood < 80:
            return "collect_wood"
        if observation.stone < 80:
            return "collect_stone"
        if observation.free_tiles > 0 and levels.get("farm", 0) < 3:
            return "upgrade_farm"
        if observation.free_tiles > 0 and levels.get("lumberyard", 0) < 3:
            return "upgrade_lumberyard"
        if observation.free_tiles > 0 and levels.get("quarry", 0) < 3:
            return "upgrade_quarry"
        if observation.public_order < 135 and observation.free_tiles > 0:
            return "build_house"
        if levels.get("academy", 0) < 2 and observation.wood >= 70 and observation.stone >= 70:
            return "upgrade_academy"
        if observation.food >= 70:
            return "train_soldiers"
        return "wait"

    def step(self, action: str) -> tuple[Observation, float, bool, dict[str, Any]]:
        self.step_counter += 1
        action = action if action in self.available_actions() else "wait"
        before = self._resource_snapshot()
        reward = 0.0
        upgraded_building = ""

        self._passive_income()

        if action == "collect_food":
            gain = self.random.randint(28, 45)
            self.state.food += gain
            reward += gain * 0.08
        elif action == "collect_wood":
            gain = self.random.randint(28, 45)
            self.state.wood += gain
            reward += gain * 0.08
        elif action == "collect_stone":
            gain = self.random.randint(28, 45)
            self.state.stone += gain
            reward += gain * 0.08
        elif action == "upgrade_farm":
            reward += self._upgrade_building("farm", food_cost=25, wood_cost=45, stone_cost=25, po_gain=1)
            upgraded_building = "farm"
        elif action == "upgrade_lumberyard":
            reward += self._upgrade_building("lumberyard", food_cost=25, wood_cost=25, stone_cost=45, po_gain=1)
            upgraded_building = "lumberyard"
        elif action == "upgrade_quarry":
            reward += self._upgrade_building("quarry", food_cost=25, wood_cost=35, stone_cost=35, po_gain=1)
            upgraded_building = "quarry"
        elif action == "build_house":
            reward += self._upgrade_building("house", food_cost=15, wood_cost=55, stone_cost=55, po_gain=8)
            upgraded_building = "house"
        elif action == "upgrade_academy":
            reward += self._upgrade_building("academy", food_cost=40, wood_cost=70, stone_cost=70, po_gain=3)
            upgraded_building = "academy"
        elif action == "train_soldiers":
            if self.state.food >= 70:
                self.state.food -= 70
                trained = self.random.randint(4, 8)
                self.state.soldiers += trained
                reward += trained * 0.9
            else:
                reward -= 1.5
        else:
            reward += 0.15

        reward += self.state.public_order * 0.02
        reward += self.state.soldiers * 0.04
        reward -= max(0, 2 - self.state.building_levels.get("farm", 0)) * 0.2
        reward -= max(0, 2 - self.state.building_levels.get("lumberyard", 0)) * 0.2
        reward -= max(0, 2 - self.state.building_levels.get("quarry", 0)) * 0.2

        done = self.step_counter >= self.max_steps or self.state.free_tiles <= 0
        after = self._resource_snapshot()
        info = {
            "upgraded_building": upgraded_building,
            "resource_delta": {key: after[key] - before[key] for key in before},
            "soldiers": self.state.soldiers,
        }
        return self._observation(), float(round(reward, 4)), done, info

    def _upgrade_building(self, building: str, food_cost: int, wood_cost: int, stone_cost: int, po_gain: int) -> float:
        level = int(self.state.building_levels.get(building, 0))
        multiplier = level + 1
        total_food = food_cost * multiplier
        total_wood = wood_cost * multiplier
        total_stone = stone_cost * multiplier
        if self.state.food < total_food or self.state.wood < total_wood or self.state.stone < total_stone:
            return -2.0
        if building != "academy" and self.state.free_tiles <= 0:
            return -2.5
        self.state.food -= total_food
        self.state.wood -= total_wood
        self.state.stone -= total_stone
        self.state.building_levels[building] = level + 1
        if building != "academy":
            self.state.free_tiles -= 1 if level == 0 else 0
        self.state.public_order += po_gain * multiplier
        return 6.0 + multiplier * 1.3

    def _passive_income(self) -> None:
        self.state.food += 8 + self.state.building_levels.get("farm", 0) * 5
        self.state.wood += 8 + self.state.building_levels.get("lumberyard", 0) * 5
        self.state.stone += 8 + self.state.building_levels.get("quarry", 0) * 5
        self.state.public_order += self.state.building_levels.get("house", 0)

    def _resource_snapshot(self) -> dict[str, int]:
        return {
            "food": self.state.food,
            "wood": self.state.wood,
            "stone": self.state.stone,
            "public_order": self.state.public_order,
            "free_tiles": self.state.free_tiles,
        }

    def _observation(self) -> Observation:
        return Observation(
            castle_name=self.state.castle_name,
            food=self.state.food,
            wood=self.state.wood,
            stone=self.state.stone,
            public_order=self.state.public_order,
            free_tiles=self.state.free_tiles,
            building_levels=dict(self.state.building_levels),
        )
