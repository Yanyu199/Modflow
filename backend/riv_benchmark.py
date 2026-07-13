"""Independent reference calculations for the RIV steady-flow benchmark."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RivBenchmarkDefinition:
    name: str
    stage: float
    conductance: float
    river_bottom: float
    nlay: int = 1
    nrow: int = 1
    ncol: int = 5
    delr: float = 100.0
    delc: float = 100.0
    top: float = 10.0
    bottom: float = 0.0
    hydraulic_conductivity: float = 1.0
    left_chd_head: float = 10.0
    right_chd_head: float = 9.0
    initial_head: float = 9.5
    head_abs_tolerance: float = 1.0e-8
    head_rel_tolerance: float = 1.0e-9
    budget_abs_tolerance: float = 1.0e-7
    percent_discrepancy_tolerance: float = 1.0e-5

    @property
    def thickness(self):
        return self.top - self.bottom

    @property
    def horizontal_conductance(self):
        return self.hydraulic_conductivity * self.delc * self.thickness / self.delr


def riv_head_above_bottom_definition():
    return RivBenchmarkDefinition(
        name="riv-head-above-bottom",
        stage=9.6,
        conductance=5.0,
        river_bottom=8.0,
    )


def riv_bottom_limited_definition():
    return RivBenchmarkDefinition(
        name="riv-bottom-limited",
        stage=9.6,
        conductance=5.0,
        river_bottom=9.55,
    )


def expected_heads(definition: RivBenchmarkDefinition):
    conductance = definition.horizontal_conductance
    river_ratio = definition.conductance / conductance

    if definition.name == "riv-head-above-bottom":
        matrix = np.array(
            [
                [-2.0, 1.0, 0.0],
                [1.0, -(2.0 + river_ratio), 1.0],
                [0.0, 1.0, -2.0],
            ],
            dtype=float,
        )
        rhs = np.array(
            [
                -definition.left_chd_head,
                -river_ratio * definition.stage,
                -definition.right_chd_head,
            ],
            dtype=float,
        )
    else:
        river_q = definition.conductance * (definition.stage - definition.river_bottom)
        matrix = np.array(
            [
                [-2.0, 1.0, 0.0],
                [1.0, -2.0, 1.0],
                [0.0, 1.0, -2.0],
            ],
            dtype=float,
        )
        rhs = np.array(
            [
                -definition.left_chd_head,
                -river_q / conductance,
                -definition.right_chd_head,
            ],
            dtype=float,
        )

    interior = np.linalg.solve(matrix, rhs)
    return np.array(
        [
            [
                [
                    definition.left_chd_head,
                    interior[0],
                    interior[1],
                    interior[2],
                    definition.right_chd_head,
                ]
            ]
        ],
        dtype=float,
    )


def expected_riv_exchange(definition: RivBenchmarkDefinition, heads=None):
    heads = expected_heads(definition) if heads is None else heads
    middle_head = float(heads[0, 0, 2])
    if middle_head > definition.river_bottom:
        return definition.conductance * (definition.stage - middle_head)
    return definition.conductance * (definition.stage - definition.river_bottom)


def expected_chd_budget(definition: RivBenchmarkDefinition, heads=None):
    heads = expected_heads(definition) if heads is None else heads
    conductance = definition.horizontal_conductance
    left_q = conductance * (definition.left_chd_head - float(heads[0, 0, 1]))
    right_q = conductance * (definition.right_chd_head - float(heads[0, 0, 3]))
    return {
        "left": left_q,
        "right": right_q,
        "in": sum(q for q in (left_q, right_q) if q > 0.0),
        "out": sum(-q for q in (left_q, right_q) if q < 0.0),
    }
