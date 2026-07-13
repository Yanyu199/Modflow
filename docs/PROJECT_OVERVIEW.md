# 2026-07-13 RIV Boundary v1 Update

The formal steady-flow path now includes cell-based RIV boundaries. RIV is stored in `flow_model_v1` under `boundaries.riv`, validated by the Model Checker, compiled into `ModflowGwfriv`, written as `gwf.riv`, and reported in `run_manifest_v1` package-budget diagnostics when present. The frontend Flow page can create/edit/delete RIV grid-cell records with stage, conductance, and river bottom.

The old line-boundary RIV UI is no longer the formal RIV workflow. It is disabled in the line-boundary panel, and the legacy backend adapter rejects RIV records that do not explicitly provide conductance and river bottom.

# 2026-07-13 Run Manifest v1 Update

The project now has the first persistent run record for the formal steady-flow path. `run_manifest_v1` stores one MODFLOW 6 execution under `backend/projects/<project_id>/runs/<run_id>/`, including input files, listing files, head/budget outputs, stdout/stderr logs, MF6 executable metadata, model snapshots, convergence diagnostics, water budget, package budget, and output registry.

The normal run flow now has project-level run history endpoints and the frontend analysis page can show the latest run summary and recent runs. The deprecated `/run-model` formal path delegates to the same RunService path when a `flow_model_id` is supplied.

# 2026-07-13 Flow Model v1 Update

The project now has a first persistent `flow_model_v1` for the steady-flow workflow. The formal Flow Model path covers IC, NPF, CHD, WEL, RIV, IMS, and OC, stores the active model at `backend/projects/<project_id>/flow/flow_model.json`, and updates `project.references.flow_model_id`.

The normal `/run-model` request now uses `project_id`, `grid_model_id`, and `flow_model_id`. In this path, the saved Flow Model is the authority for IC, K, CHD, WEL, RIV, solver, and output control. Request-body overrides for legacy `params`, `boundary_conditions`, `wells`, `k_cells`, `rch_data`, and `evt_data` are rejected when `flow_model_id` is supplied. A deprecated legacy adapter remains only behind `allow_legacy_flow_model=true`.

The frontend Flow page now supports selecting WEL, K, CHD, and RIV cells, saving/checking the Flow Model, previewing package summary, and enabling run only after the checker reports the model is runnable.

Still not implemented in the formal Flow Model: DRN, GHB, RCH, EVT, STO, transient flow, MODPATH, and GWT. Run manifest and basic run history are implemented for the first steady-flow scope.

# Project Overview

审计日期：2026-07-12  
最近实现更新：2026-07-13，新增 `grid_model` schema v1.0、稳定 `cell_id`、后端权威 DIS 网格、Grid Store artifact 和前端 Grid API 接入。

## 项目定位

本项目当前是一个地下水数值建模功能原型，目标方向是基于 MODFLOW 6 和 FloPy 的 GMS-like groundwater-flow workflow。当前代码已经把若干关键环节串成了端到端链路：导入边界和钻孔、生成结构化网格、构建 FloPy/MODFLOW 6 模型、运行后读取水头和预算文件，并用 Three.js 展示三维单元、水头颜色和局部流向。

项目尚未达到生产级数值建模软件要求。尤其需要注意：页面上存在的部分源汇项功能不一定真正进入 FloPy package；部分后端能力没有被 UI 接入；流场配置和运行历史还没有正式 schema。项目定义、地质模型和结构化网格模型已经可以后端持久化，运行目录也已改为独立目录并可保留诊断材料。

## 实际阅读文件

后端源代码和相关原型文件：

- `backend/app.py`
- `backend/export_utils.py`
- `backend/geological_builder.py`
- `backend/geology_limits.py`
- `backend/geology_model_schema.py`
- `backend/geology_model_service.py`
- `backend/geology_model_store.py`
- `backend/grid_model_schema.py`
- `backend/grid_model_service.py`
- `backend/grid_model_store.py`
- `backend/geometry_tools.py`
- `backend/geometry_utils.py`
- `backend/mf6_wrapper.py`
- `backend/modflow_engine.py`
- `backend/post_process.py`
- `backend/off.py`
- `backend/off_pandas.py`
- `backend/viewer.py`
- `backend/web_viewer.py`
- `backend/word.py`
- `backend/yanzheng.py`
- `backend/requirements.txt`
- `backend/temp_model/*`
- `backend/0`
- `backend/3.4.3`
- `backend/target_layer_id]`
- `backend/坐标.txt`
- `backend/坐标 - 副本.txt`
- `backend/1-基本顶.obj`
- `backend/1-基本顶out.off`
- `backend/output.off`
- `backend/output_data.xlsx`
- `backend/extracted_intersection_mesh.xlsx`

前端源代码和配置：

- `frontend/package.json`
- `frontend/webpack.config.js`
- `frontend/public/index.html`
- `frontend/src/main.js`
- `frontend/src/App.vue`
- `frontend/src/components/AnalysisPanel.vue`
- `frontend/src/components/AttributeManager.vue`
- `frontend/src/components/BoundaryMap.vue`
- `frontend/src/components/BoundaryPanel.vue`
- `frontend/src/components/CellDetailPanel.vue`
- `frontend/src/components/ControlPanel.vue`
- `frontend/src/components/DetailModal.vue`
- `frontend/src/components/GridSettings.vue`
- `frontend/src/components/LayerPanel.vue`
- `frontend/src/components/LayerVisibilityPanel.vue`
- `frontend/src/components/LegendPanel.vue`
- `frontend/src/components/ModelParametersPanel.vue`
- `frontend/src/components/RchEvtManager.vue`
- `frontend/src/components/Real3DViewer.vue`
- `frontend/src/components/ViewerControls.vue`
- `frontend/src/components/ViewerTopBar.vue`

仓库根目录和运行说明：

- `.gitignore`
- `启动.txt`
- `flopy开发记录.txt`
- `mf6.6.3_win64/*` 的目录结构和前若干文件
- `modpath7/*` 的目录结构和前若干文件

未完整阅读第三方依赖源码：

- `frontend/node_modules/*`
- `frontend/dist/*`
- `.git/*`
- `.idea/*`

## 当前主要技术结构

前端：

- Vue 2.7、Element UI、Three.js、Plotly、Axios。
- 项目上下文由 `App.vue` 的 `currentProject` 统一持有，并通过 `projectId` prop 传给子组件。
- API 地址多处硬编码为 `http://localhost:5000`。
- 项目定义使用 `modflow_project` schema v1.1，可由后端保存到 `backend/projects/<project_id>/project.json`，并引用 active `geology_model_id/grid_model_id/flow_model_id`。
- 地质模型使用 `geology_model` schema v1.0，可由后端保存到 `backend/projects/<project_id>/geology/geology_model.json`；前端新项目包导出为 `project + geology_model + state`。
- 网格模型使用 `grid_model` schema v1.0，可由后端保存到 `backend/projects/<project_id>/grid/grid_model.json` 和 `grid/artifacts/grid_arrays.npz`；前端 2D/3D 网格显示来自后端 `render-data`。

后端：

- Flask + Flask-CORS。
- FloPy 创建 MODFLOW 6 GWF 模型。
- GeoPandas/Shapely 解析边界和分区 Shapefile。
- SciPy RBF/griddata 根据钻孔生成地层顶底板。
- `GEO_MODELS` 全局字典仍缓存 `GeologicalModeler`，但现在只是可重建缓存：权威地质数据来自持久化 `geology_model.json`。
- `ProjectStore` 文件存储保存正式项目定义，进程重启后可重新读取项目元数据。
- `GeologyModelStore` 文件存储保存 active geology model，进程重启或清空缓存后可由标准化钻孔/地层/断层/插值参数重建。
- `GridModelStore` 文件存储保存 active structured DIS grid manifest 和数组 artifact，进程重启后可校验 checksum 并恢复 `top/botm/idomain/cell_id`。
- MF6 运行目录使用 `backend/workspace/<run-id>`，失败默认保留，成功保留由环境变量控制。

## 已真正实现的核心功能

以下功能从代码层面可以确认存在完整或近完整链路：

- 上传边界 Shapefile ZIP，读取第一个 `.shp` 的首个几何对象，转为边界坐标。
- 上传钻孔 CSV/XLSX，读取钻孔、坐标、分层、高程或厚度，构建 `GeologicalModeler`。
- 将边界、钻孔、地层、断层和插值参数标准化为 `geology_model`，进行后端校验、诊断和持久化。
- 根据 active geology model 生成后端唯一结构化 DIS 网格，并持久化为 `grid_model`。
- 使用单元 polygon 与边界 polygon 的相交面积生成 `active_2d`，而不再把单元中心点作为权威激活规则。
- 对每个地层 ID 插值生成 Top/Bottom 面，并强制层序不交叉。
- 保存统一 shape 的 `top (nrow,ncol)`、`botm (nlay,nrow,ncol)`、分层 `idomain (nlay,nrow,ncol)`。
- 为每个单元提供稳定 0-based `cell_id = <grid_model_id>:L<layer>:R<row>:C<column>`。
- 提供 Grid Model quality report，覆盖 shape、非有限数、负厚度、空层、连接性、边界覆盖和尺度摘要。
- 生成 MODFLOW 6 DIS、NPF、IC、OC package。
- 支持全局 K 和指定单元 K 覆盖。
- 支持 WEL package。
- 支持 CHD package。
- 正式 Flow Model 支持 cell-based RIV package；legacy line-based RIV 仅作兼容入口。
- 支持 RCHA 和 EVTA package 的后端创建，但当前 UI 数据来源不匹配。
- 运行 MODFLOW 6 后读取 `gwf.hds` 和 `gwf.bud`。
- 将水头、比流量、估算六面流量返回给前端。
- Three.js 显示三维地层单元、钻孔柱、水头色带、图层显隐、流向箭头。
- Plotly 显示平面水头等值线和剖面流场图。
- 通过后端把当前前端 `points` 导出为简单 OBJ。

## 当前状态判断

项目已经具备“可以演示的单机功能原型”，但还不是“可复核的数值建模平台”。主要原因如下：

- 数值模型目前固定为单应力期，未形成稳定流/非稳定流的明确建模语义。
- UI 中的若干能力没有真正写入 FloPy package，例如 DRN、GHB、RCH/EVT 散点导入。
- MF6 可执行文件已通过统一 resolver 处理；MODPATH 路径仍是后续技术债。
- 正常流程已不再隐式使用 `project_id='default'`；后端项目相关接口要求显式 `project_id`。
- 运行目录已改为独立目录，失败默认保留；正式 run manifest 和清理策略仍需完善。
- 已有自动化测试、Grid Model 后端/API 测试、最小稳定流数值基准和 RIV 数值基准；正式运行结果包含收敛、总体水量平衡和 package budget 诊断。
- CRS、长度单位、时间单位和流量单位已进入 Project Schema；Shapefile 边界上传会读取 CRS 并拒绝缺失或冲突。钻孔/断层 CSV 当前按用户声明的项目 CRS 解释，重投影和各 package 单位换算仍未实现。

## 需要验证的信息

- 前端 Vue 2.7 + `script setup` + webpack/vue-loader 当前组合需要持续通过 `pnpm run build` 验证。
- 不同机器上的 MF6 resolver 行为需要通过 `python -m pytest` 持续验证。
- MODPATH 运行是否可用，因为代码硬编码到 `G:\workspace\flopy-project\modpath7\bin\mpath7.exe`。
- 当前返回的六面流量是否与 MODFLOW 6 cell-by-cell budget 严格一致，需要用标准模型对照验证。
- Grid Model 已经持久化 `top/botm/idomain`；Flow Model 已覆盖 IC/NPF/CHD/WEL/RIV 的第一阶段 schema，RCH/EVT/DRN/GHB 等仍需要后续迁移和验证。
- 断层当前明确仅用于地质插值分区，不是 MODFLOW HFB；其地质合理性和数值稳定性需要用人工控制案例验证。
