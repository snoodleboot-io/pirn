"""``ModelArtifact`` — one candidate model as it sits in the registry.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from examples.domain_formats.ml_evaluation_loop.seeded_rng import SeededRng


@dataclass(frozen=True)
class ModelArtifact:
    """A safetensors-shaped artifact: one entry per tensor, plus registry metadata."""

    model_id: str
    framework: str
    task: str
    # layer_name -> {"dtype": str, "shape": list[int], "data": list[float]}
    tensors: dict[str, dict[str, Any]]
    metadata: dict[str, str]

    @classmethod
    def synthetic(cls, model_id: str, framework: str, task: str) -> ModelArtifact:
        """Build a realistic-looking safetensors artifact for a given model."""
        rng = SeededRng.for_model(model_id, "arch")

        tensors: dict[str, dict[str, Any]] = {}

        if framework == "transformer":
            n_layers = rng.choice([6, 12, 24])
            hidden = rng.choice([256, 512, 768])
            vocab = rng.choice([8000, 16000, 32000])

            tensors["embedding.weight"] = {
                "dtype": "float32",
                "shape": [vocab, hidden],
                "data": [rng.gauss(0, 0.02) for _ in range(min(vocab * hidden, 256))],
            }
            for i in range(n_layers):
                tensors[f"layer.{i}.attention.q_proj.weight"] = {
                    "dtype": "float16",
                    "shape": [hidden, hidden],
                    "data": [],
                }
                tensors[f"layer.{i}.attention.k_proj.weight"] = {
                    "dtype": "float16",
                    "shape": [hidden, hidden],
                    "data": [],
                }
                tensors[f"layer.{i}.attention.v_proj.weight"] = {
                    "dtype": "float16",
                    "shape": [hidden, hidden],
                    "data": [],
                }
                ffn_dim = hidden * 4
                tensors[f"layer.{i}.ffn.fc1.weight"] = {
                    "dtype": "float16",
                    "shape": [hidden, ffn_dim],
                    "data": [],
                }
                tensors[f"layer.{i}.ffn.fc2.weight"] = {
                    "dtype": "float16",
                    "shape": [ffn_dim, hidden],
                    "data": [],
                }
            tensors["classifier.weight"] = {
                "dtype": "float32",
                "shape": [hidden, rng.choice([2, 5, 10])],
                "data": [],
            }

        elif framework == "cnn":
            channels = [3, 64, 128, 256, 512]
            kernel = 3
            for i in range(len(channels) - 1):
                tensors[f"conv{i + 1}.weight"] = {
                    "dtype": "float32",
                    "shape": [channels[i + 1], channels[i], kernel, kernel],
                    "data": [],
                }
                tensors[f"conv{i + 1}.bias"] = {
                    "dtype": "float32",
                    "shape": [channels[i + 1]],
                    "data": [],
                }
                tensors[f"bn{i + 1}.weight"] = {
                    "dtype": "float32",
                    "shape": [channels[i + 1]],
                    "data": [],
                }
            fc_in = channels[-1] * rng.choice([4, 7, 14])
            n_classes = rng.choice([10, 100, 1000])
            tensors["fc.weight"] = {
                "dtype": "float32",
                "shape": [fc_in, n_classes],
                "data": [],
            }

        else:  # rnn
            input_size = rng.choice([64, 128, 256])
            hidden_size = rng.choice([128, 256, 512])
            n_layers = rng.choice([1, 2, 3])
            for i in range(n_layers):
                in_size = input_size if i == 0 else hidden_size
                tensors[f"rnn.weight_ih_l{i}"] = {
                    "dtype": "float32",
                    "shape": [4 * hidden_size, in_size],
                    "data": [],
                }
                tensors[f"rnn.weight_hh_l{i}"] = {
                    "dtype": "float32",
                    "shape": [4 * hidden_size, hidden_size],
                    "data": [],
                }
            tensors["output.weight"] = {
                "dtype": "float32",
                "shape": [hidden_size, rng.choice([1, 2, 5])],
                "data": [],
            }

        metadata = {
            "model_id": model_id,
            "framework": framework,
            "task": task,
            "format_version": "1.0",
            "created_by": "pirn-registry",
        }
        return cls(
            model_id=model_id,
            framework=framework,
            task=task,
            tensors=tensors,
            metadata=metadata,
        )
