# Real MF6 Performance

`backend/performance_baseline.py` remains a data-path microbenchmark. It does not prove MF6 solve performance.

Real MF6 scale testing is provided by:

```bash
cd backend
python mf6_scale_benchmark.py --case small
python mf6_scale_benchmark.py --case medium
python mf6_scale_benchmark.py --case large
```

The script creates a temporary project under `backend/workspace/mf6-scale-benchmarks`, builds a structured DIS grid, creates a steady flow model through `FlowModelService`, submits it through `LocalProcessRunExecutor`, and waits for the persisted manifest to become terminal.

Default cases:

- `small`: 1 x 1 x 10000 cells
- `medium`: 1 x 100 x 1000 cells
- `large`: 1 x 500 x 1000 cells

Each report includes:

- cells and shape
- terminal status
- total elapsed time
- MF6 run duration from manifest
- resource usage
- input/head/budget/listing file sizes
- convergence and water budget summaries

Large output directories are intentionally created under ignored workspace paths and must not be committed.

## Local Verification On 2026-07-13

Small benchmark:

- shape: 1 x 1 x 10000
- active cells: 10000
- status: `completed`
- total elapsed: 5.225 s
- MF6 duration: 0.441 s
- peak MF6 RSS: 17,539,072 bytes
- peak CPU seconds: 0.125
- input bytes: 2,472,812
- head bytes: 80,052
- budget bytes: 640,400
- listing bytes: 8,804
- normal termination: true
- water budget: total in 0.001000100009989069, total out 0.001000100009989069, percent discrepancy 0.0

Medium benchmark attempt:

- shape: 1 x 100 x 1000
- active cells: 100000
- timeout: 180 s
- status: `timed_out`
- MF6 duration before termination: 180.184 s
- peak MF6 RSS: 86,810,624 bytes
- peak CPU seconds: 177.328

This medium result is a real bottleneck report, not a successful performance
claim. It shows the timeout path terminates the process tree and records
resource usage.
