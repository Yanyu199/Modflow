from run_diagnostics import parse_listing_files, parse_percent_discrepancy


def test_listing_parser_detects_normal_convergence(tmp_path):
    run_root = tmp_path
    listing = run_root / "input"
    listing.mkdir()
    (listing / "mfsim.lst").write_text("Simulation finished\nNormal termination of simulation\n", encoding="utf-8")
    (listing / "gwf.lst").write_text("PERCENT DISCREPANCY = 0.000000\n", encoding="utf-8")

    parsed = parse_listing_files(run_root, ["input/mfsim.lst", "input/gwf.lst"])

    assert parsed["state"] == "converged"
    assert parsed["converged"] is True
    assert parsed["normal_termination"] is True
    assert {"source": "input/mfsim.lst", "code": "MF6_NORMAL_TERMINATION"} in parsed["evidence"]
    assert parse_percent_discrepancy(listing / "gwf.lst") == 0.0


def test_listing_parser_detects_nonconvergence(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "mfsim.lst").write_text("normal termination\n", encoding="utf-8")
    (input_dir / "gwf.lst").write_text("outer iteration convergence failure: did not converge\n", encoding="utf-8")

    parsed = parse_listing_files(tmp_path, ["input/mfsim.lst", "input/gwf.lst"])

    assert parsed["state"] == "not_converged"
    assert parsed["converged"] is False
    assert any(item["code"] == "MF6_NON_CONVERGENCE" for item in parsed["evidence"])


def test_listing_parser_is_indeterminate_when_evidence_missing(tmp_path):
    parsed = parse_listing_files(tmp_path, ["input/missing.lst"])

    assert parsed["state"] == "indeterminate"
    assert parsed["converged"] is None
    assert parsed["warnings"][0]["code"] == "RUN_LISTING_MISSING"
