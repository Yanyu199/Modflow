# 2026-07-13 Flow Model v1 Update

Resolved or reduced:

- The formal `flow_model_v1` now exists for single-period steady-flow IC, NPF, CHD, WEL, IMS, and OC.
- Normal frontend runs no longer send legacy IC/K/CHD/WEL data directly in the `/run-model` body.
- Formal runs use the saved Flow Model and backend Grid Store as the authority.
- A Flow Model benchmark now validates heads, total inflow, total outflow, and percent discrepancy through the formal data chain.

Remaining high-priority debt:

- No `run_manifest_v1` or persistent run history yet.
- Main application run responses still do not provide a structured water-balance/convergence report.
- RIV, DRN, GHB, RCH, and EVT are not part of the formal Flow Model.
- MODPATH executable configuration is still out of scope for this update.
- The legacy `/run-model` adapter remains behind `allow_legacy_flow_model=true` and should be removed after remaining packages are migrated.

# Technical Debt

本文按数值正确性、架构、安全、并发、性能和可维护性分类。严重程度为当前审计判断，后续应由测试和运行验证修正。

## Critical

### UI 和 FloPy package 不一致

现象：

- `BoundaryPanel.vue` 提供 CHD、RIV、DRN、GHB。
- `mf6_wrapper.py` 只创建 CHD 和 RIV。
- DRN/GHB 没有创建 package。
- RIV 的 `cond_start/cond_end/rbot_start/rbot_end` UI 字段没有进入后端，后端固定为 `100` 和 `5`。
- `RchEvtManager.vue` 调用 `/upload-scatter`，后端没有该 API。
- 后端 `/upload-zone` 已实现但 UI 未接入。

风险：

- 用户以为模型包含某个边界或源汇项，但 MF6 输入文件实际没有。
- 数值结果不可解释。

建议：

- 建立“UI 字段到 FloPy package 字段”的测试。
- 未实现的 UI 先禁用或标记为不可用。
- 优先修复 RIV 参数、DRN/GHB package、RCH/EVT 数据结构。

### 可执行文件路径不可复现

现象：

- MF6 路径已由 `backend/mf6_executable.py` 统一解析，支持 `FLOPY_MF6_EXE`、`MF6_EXE_PATH`、仓库相对路径和系统 PATH。
- MODPATH 硬编码为 `G:\workspace\flopy-project\modpath7\bin\mpath7.exe`。

风险：

- MODPATH 在换机器、换盘符或部署环境后仍可能无法运行。
- 错误信息可能只表现为 simulation failed。

建议：

- 后续任务使用同样机制处理 `MP7_EXE_PATH`。
- 启动时自检 MF6/MODPATH 版本和可执行权限。
- 把路径、版本写入 run artifact。

### 运行目录被过早删除

现象：

- `modflow_engine.py` 已改为每次创建独立 workspace，失败默认保留，成功是否保留由 `FLOPY_KEEP_SUCCESSFUL_RUNS` 控制。
- 目前还没有完整的运行清理策略和 UI/API 级 run history。

风险：

- 长期运行可能积累较多保留目录。
- 主应用还没有将 run artifact 正式关联到项目。

建议：

- 默认保留最近 N 次运行。
- 成功运行也保存 manifest、输入文件、输出摘要。
- 提供显式清理 API 或后台清理策略。

### 缺少数值验收

现象：

- 没有解析 listing 中的收敛信息和 percent discrepancy。
- 没有全模型水量平衡。
- 单元六面流量由 specific discharge 估算，不等同于正式 budget 验收。

风险：

- 模型可能不收敛或不守恒，但 UI 仍显示结果。
- 用户无法判断结果可信度。

建议：

- 解析 `.lst` 和 cell budget。
- 返回 convergence status、package budget、percent discrepancy。
- 增加标准模型回归测试。

### 地质派生面 artifact 尚未持久化

现象：

- Project Schema v1.1 已建立，项目定义持久化到 `backend/projects/<project_id>/project.json`。
- 正常流程不再隐式使用 `project_id='default'`，项目相关 API 要求显式 `project_id`。
- `geology_model` schema v1.0 已建立，边界、钻孔、地层、断层、插值参数和 diagnostics 持久化到 `backend/projects/<project_id>/geology/geology_model.json`。
- `GEO_MODELS` 仍是进程内全局字典，但只作为可从持久化 geology model 重建的缓存。

风险：

- 进程重启后可重建 `GeologicalModeler`，但地层面大数组尚未作为受控 artifact 保存。
- 大型模型每次重建可能耗时，且尚未保存地层面数组 checksum/shape。
- 多进程部署时每个进程会有自己的 `GEO_MODELS` 缓存。

建议：

- 后续把派生地层面保存为后端控制的 `.npz` 或等效 artifact，并在 geology model 中记录 artifact ID、shape、checksum 和输入 hash。
- 增加插值输出 benchmark，验证重建结果和 artifact 一致。
- 多进程/多用户前再引入数据库或共享缓存。

### Flow Model schema 尚未建立

现象：

- `Project`、`GeologyModel` 和 `GridModel` 已建立正式 schema。
- `/run-model` 已强制使用 `grid_model_id` 和 Grid Store 中的 `top/botm/idomain`。
- IC、NPF、CHD、WEL、RCH、EVT、RIV 等参数仍通过 legacy 请求体和前端 state 传入。

风险：

- 保存/打开项目后仍不能保证复现同一套 MF6 package 输入。
- UI 字段到 FloPy package 字段缺少统一 schema 和写入测试。

建议：

- 下一步建立 `flow_model_v1` 和最小 Model Checker。
- 先覆盖稳定流 IC/NPF/CHD/WEL，再扩展 RIV/DRN/GHB/RCH/EVT。
- 每个 package 都要有 schema、API、序列化、FloPy 写入和基准测试。

## High

### Flow 业务选择仍未完全迁移到正式 cell_id/schema

现象：

- 后端 `grid_model` v1.0 已提供稳定 `cell_id`，前端井/K 点选已优先使用后端 `cell_id`。
- `BoundaryMap.previewGrid()` 仍作为旧 fallback 存在，但正常生成网格入口已调用 Grid API。
- 边界线段配置、RCH/EVT、正式 Flow package 参数还没有统一迁移到 `flow_model_v1`。

风险：

- 旧项目或边界/source-sink 配置仍可能携带 row/col 或几何片段，而不是可校验的 cell reference。
- 重建 Grid Model 后，旧 cell_id 引用会失效，需要正式迁移/清理策略。

建议：

- 建立 `flow_model_v1` 后，把井、K、CHD/RIV/DRN/GHB/RCH/EVT 全部迁移到明确 cell/geometry reference。
- 对重建 grid 后的旧引用提供 Model Checker 提示和批量清理。

### CRS 和单位缺失

现象：

- Project Schema v1.1 已要求 CRS、水平长度、垂直长度、时间和流量单位。
- Shapefile CRS 未保存或校验。
- DIS 写 `METERS`，TDIS 写 `DAYS`，当前 schema 只接受 `m/day/m3/day`，不做转换。
- WEL、RCH、EVT UI 文案有单位，但 API 没有验证。

风险：

- 坐标单位和水文参数单位不一致时，结果数量级错误。

建议：

- 上传数据时报告 CRS 和坐标范围。
- 不同 CRS 数据必须拒绝或显式转换。
- 给每个 package 增加单位校验和错误提示。

### 初始水头策略不明确

现象：

- `ModflowGwfic` 的 `strt` 强制使用顶板 top_layer。
- UI 没有 IC 设置。

风险：

- 对非稳定流或干湿转换场景尤其危险。
- 可能掩盖边界水头极不合理的问题。

建议：

- 增加 IC 配置。
- 默认值与模型类型绑定，并在日志中明确。

### 地层和 idomain 处理过于粗糙

现象：

- Grid Model 已保存分层 `idomain`，并按 `minimum_thickness` 将薄层单元 deactivate。
- 质量报告会阻塞负厚度和地层面交叉。
- 地质插值阶段仍有最小厚度/层序处理策略，尚缺更多人工地质基准。

风险：

- 地质模型和水流模型不一致。
- 极薄层可能导致数值不稳定或非物理连通。

建议：

- 定义最小厚度规则和 inactive 规则。
- 将地质尖灭处理写入 DIS/idomain 测试。
- 增加含尖灭、断层台阶和多钻孔控制面的标准 geology/grid benchmark。

### 项目保存/打开不是正式持久化

现象：

- 正式项目定义已使用 `modflow_project` schema v1.1，正式引用 active `grid_model_id`。
- 前端下载的项目包为 `modflow_project_bundle`，新格式包含 `project`、`geology_model` 和当前流场 UI state。
- 地质体已有正式 schema 和后端持久化。
- Grid Model 已有正式 schema、manifest、`.npz` artifact 和 checksum。
- 流场配置和运行历史还没有各自的正式 schema。

风险：

- 二进制 XLSX、Shapefile 原文件和运行结果不能可靠托管。
- 打开旧 JSON 需要用户补充项目 CRS/单位，不能完全自动迁移。

建议：

- 保存源文件引用或后端托管文件。
- 建立 `flow_model_v1` 和 run manifest。
- 保存运行历史和结果摘要。

## Medium

### 上传安全和输入校验不足

现象：

- 地质模型相关 ZIP 已检查路径穿越和大小限制；其他上传入口仍需逐一复核。
- geology model 相关 API 已有 schema diagnostics；流场相关 API 多数仍直接访问字段并捕获异常。
- Flask `debug=True` 且 `host='0.0.0.0'`。
- CORS 全开放。

风险：

- 本地原型阶段尚可，但部署会有文件和调试接口风险。

建议：

- 安全解压。
- 限制文件大小和扩展名。
- 生产环境关闭 debug，限制 CORS。

### 依赖未锁定

现象：

- `backend/requirements.txt` 未固定版本。
- 前端有 `pnpm-lock.yaml`，但 Python 环境不可复现。

风险：

- FloPy、GeoPandas、Shapely、SciPy 版本变化可能改变行为。

建议：

- 使用锁文件或环境文件。
- 记录 MF6/FloPy/Python/OS 版本到 run manifest。

### 性能瓶颈

现象：

- 多处双重循环遍历所有网格单元和 boundary/zone。
- Shapely 点包含判断逐 cell 执行。
- 前端每次 points 变化重建全部 instanced mesh。

风险：

- 网格稍大时预览、运行准备和渲染变慢。

建议：

- 对 polygon bounds 和空间索引做优化。
- 后端返回网格定义和属性数组，前端增量更新。
- 建立网格规模性能基准。

### 结果图仍是展示级

现象：

- Plotly contour 直接使用散点 x/y/z，未显式构造规则矩阵和 inactive mask。
- 剖面仅支持 row/col。

风险：

- 图像可能看起来合理，但不一定严格反映模型网格。

建议：

- 用后端 grid shape 重建矩阵。
- masked contour。
- 任意线剖面从模型单元采样。

## Low

### 原型遗留文件混在后端目录

现象：

- `off.py`、`viewer.py`、`word.py`、`yanzheng.py` 是离线实验脚本。
- 后端目录含 OBJ/OFF/XLSX 输出文件、空文件和临时模型文件。

风险：

- 新开发者难以区分产品代码和实验代码。
- 可能误执行脚本写入文件。

建议：

- 建立 `experiments/` 或 `archive/`。
- 产品后端只保留 Flask 和建模核心。
- 更新 `.gitignore` 并清理未跟踪产物。

### UI 状态和 props 未完整接线

现象：

- `Real3DViewer` 接收 `rchData/evtData/showRchContour/showEvtContour`，但 `App.vue` 没有传入。
- `CellDetailPanel` 的 `trace-particle` 没有被 `Real3DViewer` 转发。
- `DetailModal.vue` 未发现接入主流程。

风险：

- 页面控件存在但无效，用户误判功能完成度。

建议：

- 建立组件事件测试。
- 未接线组件先移除或禁用。

## Recommended Immediate Fix Order

1. 建立后端唯一网格定义、稳定 `cell_id` 和地质网格质量检查。
2. 为主应用运行增加正式 run manifest 和清理策略。
3. 修复 MODPATH 路径配置和启动自检。
4. 禁用或补齐 UI-only 功能：DRN/GHB/RCH/EVT/MODPATH。
5. 将更多 package 纳入标准模型回归测试。
