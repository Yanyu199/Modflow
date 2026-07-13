"""Structured MODFLOW 6 run diagnostics."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import flopy
import numpy as np

from grid_model_schema import file_checksum


NORMAL_PATTERNS = [
    re.compile(r"\bNORMAL\s+TERMINATION\b", re.IGNORECASE),
    re.compile(r"\bSIMULATION\s+TERMINATED\s+NORMALLY\b", re.IGNORECASE),
]
NON_CONVERGENCE_PATTERNS = [
    re.compile(r"\bFAILED\s+TO\s+CONVERGE\b", re.IGNORECASE),
    re.compile(r"\bDID\s+NOT\s+CONVERGE\b", re.IGNORECASE),
    re.compile(r"\bCONVERGENCE\s+FAILURE\b", re.IGNORECASE),
    re.compile(r"\bNO\s+CONVERGENCE\b", re.IGNORECASE),
]
PERCENT_DISCREPANCY_PATTERNS = [
    re.compile(r"PERCENT\s+DISCREPANCY\s*=\s*([-+0-9.Ee]+)", re.IGNORECASE),
    re.compile(r"PERCENT_DISCREPANCY\s*=\s*([-+0-9.Ee]+)", re.IGNORECASE),
]


def _logical(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def parse_listing_files(run_root: Path, logical_files: Iterable[str]) -> Dict:
    evidence = []
    warnings = []
    normal = False
    not_converged = False
    for logical in logical_files:
        path = run_root / logical
        if not path.exists():
            warnings.append({"code": "RUN_LISTING_MISSING", "source": logical, "message": "Listing file is missing."})
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in NORMAL_PATTERNS:
            if pattern.search(text):
                normal = True
                evidence.append({"source": logical, "code": "MF6_NORMAL_TERMINATION"})
                break
        for pattern in NON_CONVERGENCE_PATTERNS:
            if pattern.search(text):
                not_converged = True
                evidence.append({"source": logical, "code": "MF6_NON_CONVERGENCE"})
                break
    if not_converged:
        state = "not_converged"
        converged = False
    elif normal:
        state = "converged"
        converged = True
    else:
        state = "indeterminate"
        converged = None
        warnings.append({
            "code": "RUN_CONVERGENCE_INDETERMINATE",
            "message": "Could not determine solver convergence from listing files.",
        })
    return {
        "state": state,
        "converged": converged,
        "normal_termination": normal,
        "evidence": evidence,
        "warnings": warnings,
    }


def parse_percent_discrepancy(listing_file: Path):
    if not listing_file.exists():
        return None
    text = listing_file.read_text(encoding="utf-8", errors="ignore")
    values = []
    for pattern in PERCENT_DISCREPANCY_PATTERNS:
        values.extend(float(match) for match in pattern.findall(text))
    return abs(values[-1]) if values else None


def _sum_budget_records(records):
    total_in = 0.0
    total_out = 0.0
    for record in records:
        if record is None or "q" not in (record.dtype.names or ()):
            continue
        q_values = np.asarray(record["q"], dtype=float)
        total_in += float(q_values[q_values > 0.0].sum())
        total_out += float(-q_values[q_values < 0.0].sum())
    return total_in, total_out


def read_package_budget(budget_file: Path, package_names=("CHD", "WEL")) -> Dict:
    if not budget_file.exists():
        return {
            "state": "unavailable",
            "packages": [],
            "warnings": [{"code": "RUN_BUDGET_MISSING", "message": "Budget file is missing."}],
        }
    budget = flopy.utils.CellBudgetFile(str(budget_file))
    kstpkper_values = budget.get_kstpkper()
    times = budget.get_times()
    if not kstpkper_values:
        return {
            "state": "unavailable",
            "packages": [],
            "warnings": [{"code": "RUN_BUDGET_EMPTY", "message": "Budget file has no time steps."}],
        }
    last_kstpkper = kstpkper_values[-1]
    packages = []
    warnings = []
    for name in package_names:
        try:
            records = budget.get_data(kstpkper=last_kstpkper, text=name)
        except Exception:
            records = []
        if not records:
            packages.append({"name": name, "available": False, "in": None, "out": None, "net": None})
            warnings.append({"code": "RUN_PACKAGE_BUDGET_MISSING", "package": name, "message": f"{name} budget is not available."})
            continue
        total_in, total_out = _sum_budget_records(records)
        packages.append({
            "name": name,
            "available": True,
            "in": total_in,
            "out": total_out,
            "net": total_in - total_out,
        })
    return {
        "state": "available",
        "kstp": int(last_kstpkper[0]) + 1,
        "kper": int(last_kstpkper[1]) + 1,
        "totim": float(times[-1]) if times else None,
        "packages": packages,
        "warnings": warnings,
    }


def read_water_budget(
    budget_file: Path,
    model_listing_file: Path,
    *,
    time_unit="day",
    flow_unit="m3/day",
    percent_tolerance=1.0e-5,
    absolute_tolerance=1.0e-7,
) -> Tuple[Dict, Dict]:
    package_budget = read_package_budget(budget_file)
    if package_budget["state"] != "available":
        return {
            "state": "unavailable",
            "kstp": None,
            "kper": None,
            "totim": None,
            "time_unit": time_unit,
            "flow_unit": flow_unit,
            "total_in": None,
            "total_out": None,
            "difference": None,
            "percent_discrepancy": None,
            "tolerance": {
                "percent_discrepancy": percent_tolerance,
                "absolute_difference": absolute_tolerance,
            },
            "within_tolerance": None,
        }, package_budget
    available = [item for item in package_budget["packages"] if item.get("available")]
    total_in = float(sum(item["in"] for item in available))
    total_out = float(sum(item["out"] for item in available))
    difference = total_in - total_out
    percent_discrepancy = parse_percent_discrepancy(model_listing_file)
    within = (
        percent_discrepancy is not None
        and abs(percent_discrepancy) <= percent_tolerance
        and abs(difference) <= absolute_tolerance
    )
    state = "available" if within else "out_of_tolerance"
    if percent_discrepancy is None:
        state = "unavailable"
        package_budget.setdefault("warnings", []).append({
            "code": "RUN_PERCENT_DISCREPANCY_MISSING",
            "message": "Could not read percent discrepancy from model listing.",
        })
    return {
        "state": state,
        "kstp": package_budget.get("kstp"),
        "kper": package_budget.get("kper"),
        "totim": package_budget.get("totim"),
        "time_unit": time_unit,
        "flow_unit": flow_unit,
        "total_in": total_in,
        "total_out": total_out,
        "difference": difference,
        "percent_discrepancy": percent_discrepancy,
        "tolerance": {
            "percent_discrepancy": percent_tolerance,
            "absolute_difference": absolute_tolerance,
        },
        "within_tolerance": within,
    }, package_budget


def register_run_files(run_root: Path, logical_files: Dict[str, str], *, checksum=False) -> Dict:
    outputs = {}
    for key, logical in logical_files.items():
        path = run_root / logical
        item = {
            "name": logical,
            "exists": path.exists(),
            "size_bytes": int(path.stat().st_size) if path.exists() else None,
        }
        if checksum and path.exists() and path.is_file():
            item["sha256"] = file_checksum(path)
        outputs[key] = item
    return outputs


def validate_head_file(head_file: Path) -> Tuple[bool, str]:
    if not head_file.exists():
        return False, "head file is missing"
    try:
        data = flopy.utils.HeadFile(str(head_file)).get_data()
        if not np.isfinite(data).all():
            return False, "head file contains NaN or Infinity"
        return True, ""
    except Exception as exc:
        return False, str(exc)


def validate_budget_file(budget_file: Path) -> Tuple[bool, str]:
    if not budget_file.exists():
        return False, "budget file is missing"
    try:
        flopy.utils.CellBudgetFile(str(budget_file))
        return True, ""
    except Exception as exc:
        return False, str(exc)
