import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import flopy
import numpy as np

from mf6_executable import ExecutableResolutionError, resolve_mf6_executable
from run_workspace import create_run_workspace


BENCHMARK_WORKSPACE_ROOT = Path(__file__).resolve().parent / "workspace" / "benchmarks"


@dataclass(frozen=True)
class SteadyFlowBenchmarkDefinition:
    name: str = "steady-flow-1lay-1row-5col-chd-wel"
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
    well_rate: float = -1.0
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


@dataclass(frozen=True)
class SteadyFlowBenchmarkResult:
    success: bool
    run_id: str
    work_dir: str
    mf6_executable: str
    mf6_source: str
    heads: list
    expected_heads: list
    max_abs_error: float
    max_rel_error: float
    total_in: float
    total_out: float
    percent_discrepancy: float
    listing_file: str
    model_listing_file: str
    head_file: str
    budget_file: str
    stdout: list


def benchmark_definition():
    return SteadyFlowBenchmarkDefinition()


def expected_heads(definition=None):
    definition = definition or benchmark_definition()
    conductance = definition.horizontal_conductance
    q = definition.well_rate

    # Unknowns are the three non-CHD cells. The equations are the finite-volume
    # steady groundwater balance with the well as an independent sink/source.
    matrix = np.array(
        [
            [-2.0, 1.0, 0.0],
            [1.0, -2.0, 1.0],
            [0.0, 1.0, -2.0],
        ]
    )
    rhs = np.array(
        [
            -definition.left_chd_head,
            -q / conductance,
            -definition.right_chd_head,
        ]
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


def build_steady_flow_simulation(work_dir, mf6_executable=None, definition=None):
    definition = definition or benchmark_definition()
    exe_name = mf6_executable or resolve_mf6_executable().path

    sim = flopy.mf6.MFSimulation(
        sim_name="steady_flow_benchmark",
        exe_name=exe_name,
        sim_ws=str(work_dir),
    )
    flopy.mf6.ModflowTdis(
        sim,
        nper=1,
        perioddata=[(1.0, 1, 1.0)],
        time_units="DAYS",
    )
    flopy.mf6.ModflowIms(
        sim,
        complexity="SIMPLE",
        outer_dvclose=1.0e-10,
        inner_dvclose=1.0e-10,
        outer_maximum=100,
        inner_maximum=100,
    )
    gwf = flopy.mf6.ModflowGwf(sim, modelname="gwf", save_flows=True)
    flopy.mf6.ModflowGwfdis(
        gwf,
        length_units="METERS",
        nlay=definition.nlay,
        nrow=definition.nrow,
        ncol=definition.ncol,
        delr=definition.delr,
        delc=definition.delc,
        top=definition.top,
        botm=definition.bottom,
        idomain=np.ones((definition.nlay, definition.nrow, definition.ncol), dtype=int),
    )
    flopy.mf6.ModflowGwfic(gwf, strt=definition.initial_head)
    flopy.mf6.ModflowGwfnpf(
        gwf,
        icelltype=0,
        k=definition.hydraulic_conductivity,
        save_specific_discharge=True,
    )
    flopy.mf6.ModflowGwfchd(
        gwf,
        stress_period_data={
            0: [
                [(0, 0, 0), definition.left_chd_head],
                [(0, 0, definition.ncol - 1), definition.right_chd_head],
            ]
        },
    )
    flopy.mf6.ModflowGwfwel(
        gwf,
        stress_period_data={0: [[(0, 0, 2), definition.well_rate]]},
    )
    flopy.mf6.ModflowGwfoc(
        gwf,
        head_filerecord="gwf.hds",
        budget_filerecord="gwf.bud",
        saverecord=[("HEAD", "ALL"), ("BUDGET", "ALL")],
        printrecord=[("BUDGET", "ALL")],
    )
    return sim, gwf


def _budget_record_sum(budget, text):
    try:
        records = budget.get_data(text=text)
    except Exception:
        return 0.0, 0.0
    total_in = 0.0
    total_out = 0.0
    for record in records:
        if "q" not in record.dtype.names:
            continue
        q_values = np.asarray(record["q"], dtype=float)
        total_in += float(q_values[q_values > 0].sum())
        total_out += float(-q_values[q_values < 0].sum())
    return total_in, total_out


def read_budget_totals(budget_file):
    budget = flopy.utils.CellBudgetFile(str(budget_file))
    total_in = 0.0
    total_out = 0.0
    for text in ("CHD", "WEL"):
        record_in, record_out = _budget_record_sum(budget, text)
        total_in += record_in
        total_out += record_out
    return total_in, total_out


def read_percent_discrepancy(listing_file):
    text = Path(listing_file).read_text(encoding="utf-8", errors="ignore")
    patterns = [
        r"PERCENT\s+DISCREPANCY\s*=\s*([-+0-9.Ee]+)",
        r"PERCENT_DISCREPANCY\s*=\s*([-+0-9.Ee]+)",
    ]
    matches = []
    for pattern in patterns:
        matches.extend(float(value) for value in re.findall(pattern, text))
    if not matches:
        raise AssertionError(f"No MODFLOW percent discrepancy found in {listing_file}")
    return abs(matches[-1])


def listing_indicates_normal_termination(listing_file):
    text = Path(listing_file).read_text(encoding="utf-8", errors="ignore").upper()
    return "NORMAL TERMINATION" in text


def run_steady_flow_benchmark(workspace_root=None, keep=True, mf6_env=None):
    definition = benchmark_definition()
    workspace_root = Path(workspace_root).resolve() if workspace_root else BENCHMARK_WORKSPACE_ROOT
    run_id, work_dir = create_run_workspace(prefix="steady-flow-benchmark", workspace_root=workspace_root)

    try:
        resolution = resolve_mf6_executable(env=mf6_env)
    except ExecutableResolutionError:
        raise

    sim, _ = build_steady_flow_simulation(work_dir, mf6_executable=resolution.path, definition=definition)
    sim.write_simulation()
    success, stdout = sim.run_simulation(silent=True, report=True)

    work_path = Path(work_dir)
    head_file = work_path / "gwf.hds"
    budget_file = work_path / "gwf.bud"
    listing_file = work_path / "mfsim.lst"
    model_listing_file = work_path / "gwf.lst"

    heads = flopy.utils.HeadFile(str(head_file)).get_data()
    expected = expected_heads(definition)
    abs_diff = np.abs(heads - expected)
    rel_diff = abs_diff / np.maximum(np.abs(expected), 1.0e-30)
    total_in, total_out = read_budget_totals(budget_file)
    percent_discrepancy = read_percent_discrepancy(model_listing_file)

    result = SteadyFlowBenchmarkResult(
        success=bool(success),
        run_id=run_id,
        work_dir=str(work_path),
        mf6_executable=resolution.path,
        mf6_source=resolution.source,
        heads=heads.tolist(),
        expected_heads=expected.tolist(),
        max_abs_error=float(abs_diff.max()),
        max_rel_error=float(rel_diff.max()),
        total_in=total_in,
        total_out=total_out,
        percent_discrepancy=percent_discrepancy,
        listing_file=str(listing_file),
        model_listing_file=str(model_listing_file),
        head_file=str(head_file),
        budget_file=str(budget_file),
        stdout=list(stdout or []),
    )

    manifest = {
        "definition": asdict(definition),
        "result": asdict(result),
        "normal_termination": listing_indicates_normal_termination(listing_file),
    }
    (work_path / "benchmark_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    # The benchmark intentionally keeps successful runs by default so failed
    # assertions still leave all MODFLOW input/output files for inspection.
    if not keep:
        from run_workspace import cleanup_run_workspace

        cleanup_run_workspace(work_path, success=success, keep_success=False)
    return result


def finite(value):
    return not (math.isnan(value) or math.isinf(value))
