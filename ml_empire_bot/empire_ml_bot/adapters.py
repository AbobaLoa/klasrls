from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .schemas import Observation


class BaseGameAdapter(ABC):
    @abstractmethod
    def reset(self) -> Observation:
        raise NotImplementedError

    @abstractmethod
    def available_actions(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def expert_action(self, observation: Observation) -> str:
        raise NotImplementedError

    @abstractmethod
    def step(self, action: str) -> tuple[Observation, float, bool, dict[str, Any]]:
        raise NotImplementedError
