# Project Overview

审计日期：2026-07-12  
审计范围：本轮只审计代码和规划文档，不修改业务代码。

## 项目定位

本项目当前是一个地下水数值建模功能原型，目标方向是基于 MODFLOW 6 和 FloPy 的 GMS-like groundwater-flow workflow。当前代码已经把若干关键环节串成了端到端链路：导入边界和钻孔、生成结构化网格、构建 FloPy/MODFLOW 6 模型、运行后读取水头和预算文件，并用 Three.js 展示三维单元、水头颜色和局部流向。

项目尚未达到生产级数值建模软件要求。尤其需要注意：页面上存在的功能不一定真正进入了 FloPy package；部分后端能力没有被 UI 接入；项目保存/打开仍然是前端 JSON 的临时方案；运行目录会被删除，导致数值复核和回归测试材料丢失。

## 实际阅读文件

后端源代码和相关原型文件：

- `backend/app.py`
- `backend/export_utils.py`
- `backend/geological_builder.py`
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
- 项目定义使用 `modflow_project` schema v1.0，可由后端保存到 `backend/projects/<project_id>/project.json`；前端项目包仍是浏览器下载 JSON。

后端：

- Flask + Flask-CORS。
- FloPy 创建 MODFLOW 6 GWF 模型。
- GeoPandas/Shapely 解析边界和分区 Shapefile。
- SciPy RBF/griddata 根据钻孔生成地层顶底板。
- `GEO_MODELS` 全局字典仍缓存 `GeologicalModeler`，但现在按显式 `project_id` 隔离，且项目不存在时拒绝写入。
- `ProjectStore` 文件存储保存正式项目定义，进程重启后可重新读取项目元数据。
- MF6 运行目录使用 `backend/workspace/<run-id>`，失败默认保留，成功保留由环境变量控制。

## 已真正实现的核心功能

以下功能从代码层面可以确认存在完整或近完整链路：

- 上传边界 Shapefile ZIP，读取第一个 `.shp` 的首个几何对象，转为边界坐标。
- 上传钻孔 CSV/XLSX，读取钻孔、坐标、分层、高程或厚度，构建 `GeologicalModeler`。
- 根据边界包围盒和 X/Y 网格参数生成结构化规则网格。
- 根据单元中心是否在边界多边形内生成 `active_2d`。
- 对每个地层 ID 插值生成 Top/Bottom 面，并强制层序不交叉。
- 生成 MODFLOW 6 DIS、NPF、IC、OC package。
- 支持全局 K 和指定单元 K 覆盖。
- 支持 WEL package。
- 支持 CHD package。
- 部分支持 RIV package。
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
- 已有自动化测试和最小稳定流数值基准；主应用运行结果仍缺正式水量平衡和收敛验收。
- CRS、长度单位、时间单位和流量单位已进入 Project Schema；上传数据的 CRS 读取、重投影和各 package 单位换算仍未实现。

## 需要验证的信息

- 前端 Vue 2.7 + `script setup` + webpack/vue-loader 当前组合是否能稳定构建，需要实际执行构建验证。
- 不同机器上的 MF6 resolver 行为需要通过 `python -m pytest` 持续验证。
- MODPATH 运行是否可用，因为代码硬编码到 `G:\workspace\flopy-project\modpath7\bin\mpath7.exe`。
- 当前返回的六面流量是否与 MODFLOW 6 cell-by-cell budget 严格一致，需要用标准模型对照验证。
- 断层插值算法的地质合理性和数值稳定性需要用人工控制案例验证。
