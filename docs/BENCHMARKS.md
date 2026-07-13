# Benchmarks

## RIV Boundary Benchmarks

Updated: 2026-07-13

The first formal RIV benchmark exercises the application data path:

```text
ProjectStore
-> GridModelStore fixture
-> flow_model_v1 boundaries.riv
-> Model Checker
-> FloPy ModflowGwfriv
-> MODFLOW 6 process
-> run_manifest_v1
-> RIV package-budget diagnostics
```

Command:

```powershell
cd backend
python -m pytest tests/test_flow_riv.py -vv
```

Shared model definition:

- Grid: 1 layer, 1 row, 5 columns.
- `delr = 100 m`, `delc = 100 m`.
- `top = 10 m`, `bottom = 0 m`.
- `Kx = Ky = Kz = 1 m/day`.
- `icelltype = 0`.
- Left CHD = 10 m at `L0:R0:C0`.
- Right CHD = 9 m at `L0:R0:C4`.
- RIV = `L0:R0:C2`.
- Initial head = 9.5 m.

Branch `riv-head-above-bottom`:

| Parameter | Value |
|---|---:|
| stage | 9.6 m |
| conductance | 5.0 m2/day |
| river_bottom | 8.0 m |
| expected equation | `Qriv = conductance * (stage - head)` |

Branch `riv-bottom-limited`:

| Parameter | Value |
|---|---:|
| stage | 9.6 m |
| conductance | 5.0 m2/day |
| river_bottom | 9.55 m |
| expected equation | `Qriv = conductance * (stage - river_bottom)` |

Expected heads and exchange rates are calculated by the independent finite-volume reference implementation in `backend/riv_benchmark.py`. They are not derived from MF6 output. The integration tests assert:

- `ModflowGwfriv` is created.
- `gwf.riv` exists when RIV is present.
- `.hds` contains finite heads with expected shape.
- RIV package budget is available from `.bud`.
- Total inflow/outflow and percent discrepancy pass the documented tolerances.
- Both RIV formula branches are covered.

Tolerances:

```text
head_abs_tol = 1e-8 m
head_rel_tol = 1e-9
budget_abs_tol = 1e-7 m3/day
percent_discrepancy_tol = 1e-5
```

Run artifacts are retained by `RunService` under:

```text
backend/projects/<project_id>/runs/<run_id>/
```

Important files for RIV review:

- `run_manifest.json`
- `input/gwf.riv`
- `input/gwf.chd`
- `input/gwf.npf`
- `input/gwf.lst`
- `input/gwf.hds`
- `input/gwf.bud`
- `logs/mf6_stdout.txt`
- `logs/mf6_stderr.txt`

## Persistent Run Manifest Benchmark

Updated: 2026-07-13

The formal benchmark now exercises the full persistent run path:

```text
ProjectStore
-> GridModelStore fixture
-> flow_model_v1
-> Flow Model Checker
-> RunService
-> run_manifest_v1
-> FloPy package writer
-> MODFLOW 6 process
-> listing/head/budget diagnostics
-> Run API summary
```

Command:

```powershell
cd backend
python -m pytest tests/test_run_api.py::test_run_api_creates_persistent_manifest_and_budget_report -vv
```

The model definition is the same 1-layer, 1-row, 5-column steady-flow benchmark:

- `delr = 100 m`
- `delc = 100 m`
- `top = 10 m`
- `bottom = 0 m`
- `Kx = Ky = Kz = 1 m/day`
- `icelltype = 0`
- left CHD = 10 m
- right CHD = 9 m
- center WEL = -1 m3/day
- initial head = 9.5 m

Expected heads:

```text
[[[10.0, 9.7, 9.4, 9.2, 9.0]]]
```

Expected budget:

```text
CHD in  = 3.0 m3/day
CHD out = 2.0 m3/day
WEL out = 1.0 m3/day
total in = 3.0 m3/day
total out = 3.0 m3/day
percent discrepancy = 0.0
```

Tolerances:

```text
head_abs_tol = 1e-8 m
head_rel_tol = 1e-9
budget_abs_tol = 1e-7 m3/day
percent_discrepancy_tol = 1e-5
```

Run artifacts are retained under:

```text
backend/projects/<project_id>/runs/<run_id>/
```

Important files:

- `run_manifest.json`
- `input/mfsim.nam`
- `input/mfsim.lst`
- `input/gwf.dis`
- `input/gwf.npf`
- `input/gwf.chd`
- `input/gwf.wel`
- `input/gwf.oc`
- `input/gwf.lst`
- `input/gwf.hds`
- `input/gwf.bud`
- `logs/mf6_stdout.txt`
- `logs/mf6_stderr.txt`

Failure review starts with `run_manifest.json`, then `logs/mf6_stderr.txt`, `input/mfsim.lst`, `input/gwf.lst`, `input/gwf.hds`, and `input/gwf.bud`.

本文记录当前项目的第一个可复核运行基准：单层稳定流 MODFLOW 6 模型。该基准不依赖 Flask 开发服务器，可通过 pytest 重复运行，并保留 MODFLOW 6 输入输出文件用于复核。

## MF6 Executable Configuration

MODFLOW 6 可执行文件由 `backend/mf6_executable.py` 统一解析，查找优先级为：

1. 环境变量 `FLOPY_MF6_EXE`。
2. 兼容环境变量 `MF6_EXE_PATH`。
3. 仓库内相对路径：
   - `mf6.6.3_win64/bin/mf6.exe` on Windows, `mf6.6.3_win64/bin/mf6` on Unix-like systems。
   - `backend/bin/mf6.exe` 或 `backend/bin/mf6`。
   - `bin/mf6.exe` 或 `bin/mf6`。
4. 系统 `PATH` 中的 `mf6`。

解析器会检查候选路径是否存在并可执行。找不到时会抛出清晰错误，并列出所有已检查来源。

示例：

```powershell
$env:FLOPY_MF6_EXE="<path-to-mf6.exe>"
cd <repo>\backend
python -m pytest
```

跨机器复现时推荐使用 `FLOPY_MF6_EXE` 指向本机安装的 MF6，或把 MF6 放在上述仓库相对路径中。

## Test Installation And Commands

安装测试依赖：

```powershell
cd <repo>\backend
python -m pip install -r requirements-dev.txt
```

运行全部测试：

```powershell
cd <repo>\backend
python -m pytest
```

只运行数值集成测试：

```powershell
cd <repo>\backend
python -m pytest -m integration
```

测试不依赖 Flask 开发服务器。

## Minimal Steady-Flow Benchmark

模型名称：`steady-flow-1lay-1row-5col-chd-wel`

模型定义：

| 项目 | 数值 |
|---|---:|
| 层数 | 1 |
| 行数 | 1 |
| 列数 | 5 |
| `delr` | 100 m |
| `delc` | 100 m |
| 顶板 | 10 m |
| 底板 | 0 m |
| 厚度 | 10 m |
| K | 1 m/d |
| 左端 CHD | cell `(0, 0, 0)`, head = 10 m |
| 右端 CHD | cell `(0, 0, 4)`, head = 9 m |
| 抽水井 WEL | cell `(0, 0, 2)`, rate = -1 m3/d |
| 初始水头 | 9.5 m |
| TDIS | 1 stress period, 1 time step, `DAYS` |
| IMS | `SIMPLE`, `outer_dvclose=1e-10`, `inner_dvclose=1e-10` |
| NPF | `icelltype=0`, `save_specific_discharge=True` |
| OC | 保存全部 head 和 budget |

包含的 MODFLOW 6 package：

- TDIS
- IMS
- GWF
- DIS
- IC
- NPF
- CHD
- WEL
- OC

## Expected Head Values

该基准的水头不是从 MODFLOW 6 结果反推，而是在测试中独立求解一维稳定有限体积线性方程组。

水平单元间导水能力：

```text
C = K * delc * thickness / delr
  = 1 * 100 * 10 / 100
  = 10 m2/d
```

未知单元为第 1、2、3 列。左、右定水头单元分别为 10 m 和 9 m，中间井流量为 -1 m3/d。线性方程为：

```text
10 + h2 - 2*h1 = 0
h1 + h3 - 2*h2 + (-1 / 10) = 0
h2 + 9 - 2*h3 = 0
```

预期水头：

```text
[10.0, 9.7, 9.4, 9.2, 9.0]
```

## Expected Budget

预期水量平衡：

| 项目 | 数值 |
|---|---:|
| 左侧 CHD 流入 | 3.0 m3/d |
| 右侧 CHD 流出 | 2.0 m3/d |
| WEL 抽水流出 | 1.0 m3/d |
| 总流入 | 3.0 m3/d |
| 总流出 | 3.0 m3/d |
| 预期 percent discrepancy | 0 |

容差：

| 检查项 | 容差 |
|---|---:|
| 水头绝对误差 | `1e-8` m |
| 水头相对误差 | `1e-9` |
| 总流入/总流出绝对误差 | `1e-7` m3/d |
| MODFLOW percent discrepancy | `1e-5` |

这些预期可信的原因是模型为单层、均质、承压、规则 1D 网格，所有源汇项都是确定值，离散方程可直接手算和独立求解。

## Run Artifacts

benchmark 运行产物保存在：

```text
backend/workspace/benchmarks/steady-flow-benchmark-<run-id>/
```

目录已加入 `.gitignore`，不会作为源代码提交。每次测试使用独立目录，避免覆盖。

关键文件包括：

- `mfsim.nam`
- `steady_flow_benchmark.tdis`
- `steady_flow_benchmark.ims`
- `gwf.nam`
- `gwf.dis`
- `gwf.ic`
- `gwf.npf`
- `gwf.chd`
- `gwf.wel`
- `gwf.oc`
- `mfsim.lst`
- `gwf.lst`
- `gwf.hds`
- `gwf.bud`
- `benchmark_manifest.json`

`mfsim.lst` 用于确认 MODFLOW 6 正常结束。`gwf.lst` 用于读取模型水量平衡和 percent discrepancy。`gwf.hds` 和 `gwf.bud` 用于水头和预算复核。

## Latest Verified Run

本机最近一次验证：

| 项目 | 结果 |
|---|---:|
| MF6 来源 | `repo-relative` |
| MF6 版本 | 6.6.3 |
| 进程状态 | normal termination |
| 实际水头 | `[10.0, 9.7, 9.4, 9.2, 9.0]` |
| 最大绝对误差 | `1.7763568394002505e-15` |
| 最大相对误差 | `1.9308226515220118e-16` |
| 总流入 | `3.000000000000007` m3/d |
| 总流出 | `2.999999999999993` m3/d |
| percent discrepancy | `0.0` |

## Failure Review

如果测试失败：

1. 查看 pytest 输出中的 benchmark run directory。
2. 打开该目录下的 `benchmark_manifest.json`，确认 MF6 路径来源和实际误差。
3. 查看 `mfsim.lst`，确认是否为 normal termination。
4. 查看 `gwf.lst`，检查 solver、budget 和 percent discrepancy。
5. 用 FloPy 或 MODFLOW 工具读取 `gwf.hds` 和 `gwf.bud` 复核二进制结果。

主应用运行目录也改为每次独立创建。失败运行默认保留目录；成功运行是否保留由环境变量 `FLOPY_KEEP_SUCCESSFUL_RUNS` 控制：

```powershell
$env:FLOPY_KEEP_SUCCESSFUL_RUNS="1"
```

未设置时，主应用成功运行会清理目录，benchmark 测试会主动保留目录。
## Persistent Flow Model Benchmark

Updated: 2026-07-13

The original benchmark still exists and directly constructs a FloPy simulation. A second benchmark now verifies the formal application data path:

```text
ProjectStore
-> GridModelStore fixture
-> flow_model_v1
-> Model Checker
-> Package Compiler
-> MODFLOW 6
-> .hds/.bud/.lst validation
```

Command:

```powershell
cd backend
python -m pytest tests/test_flow_model.py::test_persistent_flow_model_benchmark_runs_and_matches -vv
```

This benchmark uses the same 1-layer, 1-row, 5-column model:

- `delr = 100 m`
- `delc = 100 m`
- `top = 10 m`
- `bottom = 0 m`
- `Kx = Ky = Kz = 1 m/day`
- `icelltype = 0`
- left CHD = 10 m
- right CHD = 9 m
- center WEL = -1 m3/day
- initial head = 9.5 m

Expected heads:

```text
[[[10.0, 9.7, 9.4, 9.2, 9.0]]]
```

The test checks package existence, normal termination, finite head values, CHD cell heads, maximum absolute and relative head errors, total inflow, total outflow, and MODFLOW percent discrepancy.

The generated files are retained by the RunService manifest store. They are written under `backend/projects/<project_id>/runs/<run_id>/input/` and include:

- `mfsim.nam`
- `sim.tdis`
- `sim.ims`
- `gwf.nam`
- `gwf.dis`
- `gwf.ic`
- `gwf.npf`
- `gwf.chd`
- `gwf.wel`
- `gwf.oc`
- `mfsim.lst`
- `gwf.lst`
- `gwf.hds`
- `gwf.bud`
