# 2026-07-13 Flow Model v1 Update

Phase 1 now has a first vertical slice for persistent single-period steady flow:

- `flow_model_v1` schema/store/service.
- Model Checker for IC, NPF, CHD, WEL, IMS, and OC.
- Package compiler that builds TDIS, IMS, GWF, DIS, IC, NPF, CHD, WEL, and OC from Grid Store and Flow Store.
- Formal `/run-model` path based on `flow_model_id`.
- End-to-end benchmark through Project/Grid/Flow/Checker/Compiler/MF6.
- Frontend Flow page path: select WEL/K/CHD cells, save/check Flow Model, then run.

`run_manifest_v1` and the first structured numerical acceptance report are now implemented for the formal steady-flow path. The next smallest vertical task should be one additional boundary package, preferably RIV, implemented end to end through schema, validation, FloPy package creation, package-budget diagnostics, UI wiring, and a small benchmark.

# Roadmap

路线图按“先让一个小而可信的 MODFLOW 6 稳定流工作流闭环，再逐步扩展”的原则制定。每个阶段都必须有数值验收，不以页面能打开作为完成标准。

## Phase 0: Baseline Audit And Reproducibility

功能范围：

- 固定当前原型的事实文档。
- 建立最小测试框架和运行 artifact 策略。
- 增加 MF6/MODPATH 可执行文件自检设计。
- 建立项目 schema 的第一版实现。

前置条件：

- 不重构业务流程。
- 保留当前前端交互作为对照。

验收标准：

- 可以在本机运行一个最小模型，并保留完整输入、输出、日志、版本信息。
- 每次运行有唯一 run id 和可查目录。
- 失败时不删除诊断文件。
- 有至少一个 smoke test 验证 Flask API 能创建 MF6 输入文件。

数值基准：

- 先使用极简矩形单层 steady CHD 模型，解析解或手算水力梯度可对照。
- 保存 head 最大误差、水量平衡误差和输入文件快照。

主要风险：

- 运行目录保留基础已建立，仍需正式 run manifest 和清理策略。
- MF6 路径已通过 resolver 和测试覆盖；仍需在正式 run manifest 中记录版本。

## Phase 1: Trusted Single-Period Steady Flow Core

功能范围：

- 单应力期稳定流。
- 结构化 DIS 网格。首版 `grid_model` v1.0 已完成，后端保存 manifest/artifact 并提供稳定 `cell_id`。
- NPF、IC、CHD、WEL。
- 水头结果和全模型水量平衡。
- 前后端共用后端返回的 Grid Model，不再让前端独立计算权威 row/col。

前置条件：

- Phase 0 的 run artifact 和测试框架完成。
- 明确长度单位、时间单位、流量单位。

验收标准：

- UI 配置的 CHD/WEL/K 能在生成的 MF6 package 文件中逐项核对。
- 运行结果包含 convergence status、listing 摘要、package budget、percent discrepancy。
- row/col/layer 从前端点击到后端 DIS 完全一致，且通过稳定 `cell_id` 传递。
- 保存项目并重新打开后，生成的 MF6 输入文件与原运行一致或差异有明确迁移说明。

数值基准：

- 单层矩形承压/潜水稳定流基准。
- 一个 CHD-CHD 梯度流测试。
- 一个 CHD + WEL 抽水测试。
- 容差建议：head 误差和 budget discrepancy 阈值需按基准模型尺度定义。

主要风险：

- 当前 IC 默认使用顶板，可能掩盖不合理边界水头。
- 当前 `icelltype=1` 会涉及可转换单元和干湿问题，需小心解释 steady 语义。

## Phase 2: Project Schema, Validation, And Persistence

功能范围：

- `Project` schema v1.0 已完成。
- `GeologyModel` schema v1.0 已完成基础版，覆盖边界、钻孔、地层、断层、插值参数、diagnostics、持久化和缓存重建。
- `GridModel` schema v1.0 已完成基础版，覆盖结构化 DIS、top/botm/idomain、cell_id、quality report、artifact checksum、stale 和 API。
- 后续继续定义 `FlowPackageConfig`、`Run` 数据结构。
- 输入验证：文件、字段、单位、坐标、层序、参数范围。
- 项目保存/打开已包含正式 project schema 和 geology model schema；流场 state 仍需迁移到正式 schema。
- 后端项目定义和地质标准数据不依赖 Flask 全局状态；`GEO_MODELS[project_id]` 只作为可重建缓存。

前置条件：

- Phase 1 核心模型闭环稳定。

验收标准：

- 项目 JSON 有 schema version。已完成 `modflow_project` v1.0 和 `geology_model` v1.0。
- 打开旧项目时有兼容路径或明确报错。
- API 对错误字段返回结构化错误。
- 单元测试覆盖 project/geology/grid schema、边界、钻孔/地层、断层、Grid API、持久化隔离、checksum、stale、cell_id 和缓存重建；K/WEL/CHD 配置仍在后续 flow schema 中扩展。

数值基准：

- 使用 Phase 1 基准模型，验证保存/打开前后 head 和 budget 完全一致。

主要风险：

- 当前地质恢复不再依赖 `rawCsvContent`，但原始 XLSX/Shapefile 文件托管和派生面 artifact 持久化仍未完成。
- 修改数据结构会影响前端多处组件，必须小步迁移。

## Phase 3: Boundary And Source/Sink Completion

功能范围：

- 完整实现 RIV、DRN、GHB。
- 统一 RCH/EVT 数据结构，支持面分区；散点插值如保留，需明确算法和验证。
- 支持 package 参数的层选择和单位检查。
- 每个 package 提供 MF6 输入文件检查测试。

前置条件：

- Phase 2 的 schema 和验证可用。
- 前后端网格索引统一。

验收标准：

- UI 中每个字段都能追踪到 FloPy package 的 stress period data。
- RIV 的 stage/cond/rbot 不再硬编码。
- DRN/GHB 创建对应 package，并在结果 budget 中出现。
- RCH/EVT 上传接口和 UI 一致。

数值基准：

- RIV/DRN/GHB/RCH/EVT 各自一个小型标准模型。
- package budget 的流入/流出方向和数量级有手算或官方示例对照。

主要风险：

- EVT 的 surface/depth 和 top elevation 关系容易导致非物理蒸发。
- 多 package 叠加时需要冲突检查，例如同一单元同时 CHD 和 WEL。

## Phase 4: Result Analysis And Numerical Acceptance

功能范围：

- 结果面板增加正式水量平衡、package budget、收敛报告。
- 等值线处理 inactive mask 和多层选择。
- 剖面分析从 row/col 扩展到任意线采样。
- 导出结果表、GeoJSON/CSV、OBJ 时记录坐标轴和单位。

前置条件：

- Phase 3 packages 有可信 budget。

验收标准：

- 每次运行有“通过/警告/失败”的数值验收状态。
- 用户能查看 head min/max、dry cell、inactive cell、budget discrepancy。
- 剖面结果可重复导出。

数值基准：

- 与 Phase 1-3 全部基准联合运行。
- 对每个结果图提供数据表导出对照。

主要风险：

- 当前六面流量由 SPDIS 推导，不足以替代 cell-by-cell budget。
- 坐标方向 X/Y/Z 到 Three.js 的映射需要系统测试。

## Phase 5: Transient Flow

功能范围：

- 多应力期 TDIS。
- Time series 或 period data for CHD/RIV/DRN/GHB/WEL/RCH/EVT。
- 存储参数 STO。
- 时间步结果浏览。

前置条件：

- 稳定流 packages 和结果验收完成。
- 项目 schema 能表达多 period。

验收标准：

- UI 能创建、编辑、保存多个 stress periods。
- MODFLOW 6 输入文件 period data 可核对。
- 前端可以按时间步查看水头、budget、等值线。

数值基准：

- Theis 或简化抽水恢复测试，需要验证。
- 官方 MODFLOW 6 transient 示例，需要验证具体示例名称和容差。

主要风险：

- UI 复杂度会显著上升。
- 时间单位、抽水率单位和存储参数必须严格一致。

## Phase 6: Geological Model Robustness

功能范围：

- 地层插值算法配置化。
- 尖灭、薄层、断层分块规则可解释。
- 局部 inactive 或最小厚度规则进入 `idomain/botm`。
- 保存地层面和插值诊断。

前置条件：

- Phase 1-4 数值核心稳定。

验收标准：

- 钻孔控制点处插值误差可报告。
- Top/Bottom 交叉、负厚度、极薄层有明确处理。
- 断层影响只作为地质几何时，UI 明确说明；如作为水力断层，需实现对应 MF6 表达。

数值基准：

- 人工三层平面模型。
- 含尖灭层模型。
- 断层两侧台阶模型。

主要风险：

- 当前 RBF 插值和强制推平可能产生地质上不合理的面。
- 地质修正会改变数值网格，需回归测试保护。

## Phase 7: MODPATH Particle Tracking

功能范围：

- 修复前端事件链路。
- 配置 MODPATH 可执行路径。
- 支持粒子释放位置、方向、porosity、tracking direction。
- 保存并展示 pathline/timeseries。

前置条件：

- MODFLOW 运行 artifact 可保留。
- Flow budget 和 specific discharge 已验收。

验收标准：

- 点击单元能触发后端 MODPATH。
- MODPATH 输入输出文件保留。
- 路径线坐标与模型坐标一致。
- 至少一个标准路径基准通过。

数值基准：

- 简单均匀流场粒子直线路径。
- 抽水井捕获区简化测试。

主要风险：

- 当前 `MP7_EXE_PATH` 硬编码。
- `process_pathlines()` 对坐标 origin 的处理需要验证。

## 推荐的下一个开发任务

建议下一个开发任务是：建立 `flow_model_v1` 和最小 Model Checker，先覆盖稳定流 IC/NPF/CHD/WEL。

原因：

- 它承接当前 `project/geology/grid` 三个 schema。
- 它能把当前 `/run-model` legacy adapter 中的 IC/NPF/CHD/WEL 参数正式持久化。
- 它是 package 写入测试、水量平衡验收和保存/打开复现 MF6 输入文件的前置条件。
