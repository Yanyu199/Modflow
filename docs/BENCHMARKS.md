# Benchmarks

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
