# Performance Baseline

Date: 2026-07-13.

Command:

```bash
cd backend
python performance_baseline.py --json
```

This is a data-path benchmark, not a large MODFLOW 6 solve benchmark. It checks
resource estimates, NumPy layer allocation, layer slicing, and binary response
size for representative cell counts.

Environment from this run:

- Platform: Windows-10-10.0.26200-SP0
- Python: 3.9.12
- Processor string: AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD

## Results

| Case | Cells | Class | Total Time s | Peak Python Memory | Binary Layer Bytes | MF6 Run? |
|---|---:|---|---:|---:|---:|---|
| small | 100,000 | small | 0.00069 | 1,610,874 | 800,000 | no |
| medium | 500,000 | medium | 0.00158 | 8,002,549 | 4,000,000 | no |
| large | 1,000,000 | large | 0.00471 | 16,002,997 | 8,000,000 | no |

## Interpretation

- The current response limit default is 8 MB, so a 1,000,000-cell single-layer
  float64 binary slice is exactly at the default response scale.
- JSON result slices are limited separately by `FLOPY_RESULT_JSON_CELL_LIMIT`
  and should be kept small.
- These numbers only show local array and serialization costs. They do not prove
  1,000,000-cell MF6 solve performance.
- Existing numerical MF6 coverage remains the small steady-flow and RIV
  benchmarks in pytest.
