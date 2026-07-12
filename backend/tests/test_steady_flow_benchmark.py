from pathlib import Path

import numpy as np
import pytest

from mf6_executable import ExecutableResolutionError
from steady_flow_benchmark import (
    benchmark_definition,
    build_steady_flow_simulation,
    expected_heads,
    listing_indicates_normal_termination,
    run_steady_flow_benchmark,
)


def test_benchmark_simulation_contains_required_packages(tmp_path):
    definition = benchmark_definition()
    sim, gwf = build_steady_flow_simulation(tmp_path, mf6_executable="mf6", definition=definition)

    package_names = {package.package_type for package in gwf.packagelist}
    assert {"dis", "ic", "npf", "chd", "wel", "oc"}.issubset(package_names)
    assert sim.get_package("tdis") is not None
    assert sim.get_package("ims") is not None

    np.testing.assert_allclose(gwf.npf.k.get_data(), definition.hydraulic_conductivity)
    chd_data = gwf.chd.stress_period_data.get_data(key=0)
    wel_data = gwf.wel.stress_period_data.get_data(key=0)

    assert tuple(chd_data[0]["cellid"]) == (0, 0, 0)
    assert chd_data[0]["head"] == pytest.approx(definition.left_chd_head)
    assert tuple(chd_data[1]["cellid"]) == (0, 0, definition.ncol - 1)
    assert chd_data[1]["head"] == pytest.approx(definition.right_chd_head)
    assert tuple(wel_data[0]["cellid"]) == (0, 0, 2)
    assert wel_data[0]["q"] == pytest.approx(definition.well_rate)


@pytest.mark.integration
def test_minimal_steady_flow_benchmark_runs_and_matches():
    definition = benchmark_definition()
    try:
        result = run_steady_flow_benchmark(keep=True)
    except ExecutableResolutionError as exc:
        pytest.skip(f"MODFLOW 6 executable not available: {exc}")

    work_dir = Path(result.work_dir)
    heads = np.array(result.heads)
    expected = expected_heads(definition)

    assert result.success is True
    assert listing_indicates_normal_termination(result.listing_file)
    for filename in (
        "mfsim.nam",
        "steady_flow_benchmark.tdis",
        "steady_flow_benchmark.ims",
        "gwf.nam",
        "gwf.dis",
        "gwf.ic",
        "gwf.npf",
        "gwf.chd",
        "gwf.wel",
        "gwf.oc",
        "gwf.lst",
        "mfsim.lst",
        "gwf.hds",
        "gwf.bud",
        "benchmark_manifest.json",
    ):
        assert (work_dir / filename).exists(), filename

    assert heads.shape == (definition.nlay, definition.nrow, definition.ncol)
    assert np.isfinite(heads).all()
    assert heads[0, 0, 0] == pytest.approx(definition.left_chd_head, abs=definition.head_abs_tolerance)
    assert heads[0, 0, definition.ncol - 1] == pytest.approx(
        definition.right_chd_head,
        abs=definition.head_abs_tolerance,
    )
    np.testing.assert_allclose(
        heads,
        expected,
        atol=definition.head_abs_tolerance,
        rtol=definition.head_rel_tolerance,
    )
    assert result.max_abs_error <= definition.head_abs_tolerance
    assert result.max_rel_error <= definition.head_rel_tolerance
    assert result.total_in == pytest.approx(3.0, abs=definition.budget_abs_tolerance)
    assert result.total_out == pytest.approx(3.0, abs=definition.budget_abs_tolerance)
    assert abs(result.total_in - result.total_out) <= definition.budget_abs_tolerance
    assert result.percent_discrepancy <= definition.percent_discrepancy_tolerance
