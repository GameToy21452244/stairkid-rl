from __future__ import annotations

import numpy as np
import torch
from torch import nn


class BehaviorCloningMLP(nn.Module):
    def __init__(self, input_dim: int = 268) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 3),
        )

    def forward(self, observation: torch.Tensor) -> torch.Tensor:
        return self.network(observation)


class BCPolicy:
    def __init__(self, model: BehaviorCloningMLP) -> None:
        self.model = model.eval()

    def predict(self, observation: np.ndarray, deterministic: bool = True):
        del deterministic
        with torch.no_grad():
            tensor = torch.as_tensor(observation, dtype=torch.float32).unsqueeze(0)
            action = int(self.model(tensor).argmax(dim=1).item())
        return action, None


__all__ = ["BCPolicy", "BehaviorCloningMLP"]
