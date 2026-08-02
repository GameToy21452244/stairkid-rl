from __future__ import annotations

import torch

from stair_agent.training.behavior_cloning import BehaviorCloningMLP


def test_bc0_architecture_outputs_three_logits() -> None:
    model = BehaviorCloningMLP()
    assert model(torch.zeros((4, 268))).shape == (4, 3)
    linear_shapes = [
        (layer.in_features, layer.out_features)
        for layer in model.network
        if isinstance(layer, torch.nn.Linear)
    ]
    assert linear_shapes == [(268, 256), (256, 128), (128, 3)]
