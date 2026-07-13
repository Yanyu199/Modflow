# 2026-07-13 Flow Model Dependency

`flow_model_v1` references Grid Model cells by stable `cell_id`. Regenerating the active Grid Model invalidates previously saved Flow Model cell references, so `GridModelService.create()` marks the active Flow Model stale when a new grid is saved.

# Grid Model Schema

更新日期：2026-07-13

## 目标

`grid_model` schema v1.0 是当前平台的正式离散化数据契约。它把结构化 DIS 网格从前端临时预览中拆出来，改为后端唯一生成、后端持久化、后端校验，并作为 `/run-model` 的权威网格来源。

职责边界：

- `Project`：项目 CRS、单位、模型类型和 active model 引用。
- `GeologyModel`：边界、钻孔、地层、断层和插值参数。
- `GridModel`：DIS 网格几何、`top`、`botm`、分层 `idomain`、稳定 `cell_id`、质量报告和数组 artifact。
- `FlowModel`：尚未正式实现，后续负责 IC/NPF/CHD/WEL/RCH/EVT 等 package 参数。

## 顶层结构

```json
{
  "schema_name": "grid_model",
  "schema_version": "1.0",
  "grid_model_id": "grid_0123456789abcdef",
  "project_id": "prj_0123456789abcdef",
  "geology_model_id": "geo_0123456789abcdef",
  "name": "Structured groundwater grid",
  "created_at": "2026-07-13T10:00:00+08:00",
  "modified_at": "2026-07-13T10:00:00+08:00",
  "grid_type": "structured_dis",
  "status": "ready",
  "generation": {},
  "geometry": {},
  "artifacts": {},
  "quality": {},
  "provenance": {}
}
```

当前只支持 `grid_type = structured_dis`。未知 schema version、跨项目 grid id、非法 artifact 路径或 checksum 不匹配都会被拒绝。

## Project Schema 迁移

Project Schema 已从 `1.0` 迁移到兼容版 `1.1`，`references` 正式包含：

```json
{
  "geology_model_id": null,
  "grid_model_id": null,
  "flow_model_id": null
}
```

旧 `1.0` 项目读取时会显式迁移为 `1.1` 并原子写回，不丢失原字段。`grid_model_id` 不放入 `metadata`，避免绕过 schema 版本管理。

## 生成配置

Grid API 接受的首版配置：

```json
{
  "grid_type": "structured_dis",
  "cell_size": {"x": 100.0, "y": 100.0},
  "rotation": 0.0,
  "minimum_thickness": 0.1,
  "pinchout_policy": "deactivate",
  "boundary_activation_rule": "cell_intersection",
  "minimum_boundary_overlap": 0.1
}
```

兼容旧前端字段 `x_val/y_val`，但正常新流程会转换为 `cell_size.x/y`。后端不接受前端提交 `top`、`botm` 或 `idomain` 来覆盖权威数组。

资源限制集中在 `backend/grid_model_schema.py`：

- `MAX_NLAY = 200`
- `MAX_NROW = 1000`
- `MAX_NCOL = 1000`
- `MAX_TOTAL_CELLS = 1_000_000`
- `MIN_CELL_SIZE = 1.0e-6`
- `MAX_ARTIFACT_BYTES = 512 MiB`
- `MAX_RENDER_CELLS = 200_000`

## 数组和 artifact

文件布局：

```text
backend/projects/<project_id>/grid/
├── grid_model.json
└── artifacts/
    └── grid_arrays.npz
```

`grid_arrays.npz` 至少保存：

```text
delr
delc
top
botm
idomain
x_centers
y_centers
overlap_ratio
thickness
```

统一 shape：

```python
top.shape == (nrow, ncol)
botm.shape == (nlay, nrow, ncol)
idomain.shape == (nlay, nrow, ncol)
```

manifest 只保存数组 metadata、相对 artifact 路径、文件 checksum 和数组 checksum，不把大数组写入 JSON。API 不接受客户端路径，也不返回服务器绝对路径。

## 边界激活规则

首版实现 `boundary_activation_rule = cell_intersection`。每个二维单元构造 polygon，与 geology boundary 求相交面积：

```text
overlap_ratio = intersection_area / cell_area
active_2d = overlap_ratio >= minimum_boundary_overlap
```

这替代旧的“单元中心点是否在 polygon 内”规则，能处理中心在边界外但单元与狭窄边界明显相交的情况。`Polygon` 和 `MultiPolygon` 由 Shapely 处理；内洞支持仍需要更完整 UI 和基准验证。

## top/botm/idomain

`top` 和 `botm` 来自同一个 active `geology_model` 及其插值参数。每层 `idomain` 独立计算：

- 二维边界激活状态；
- top/bottom 是否有限；
- 本层厚度；
- `minimum_thickness`；
- `pinchout_policy = deactivate`。

厚度小于 `minimum_thickness` 的单元设为 inactive。负厚度和地层面交叉是阻塞错误，不会通过取绝对值、交换上下界或强制加厚来静默修复。

## cell_id

每个单元使用 0-based 稳定 ID：

```text
<grid_model_id>:L<layer>:R<row>:C<column>
```

示例：

```text
grid_abcd1234abcd1234:L0:R12:C18
```

后端集中提供生成和解析函数，严格校验 grid id、layer、row、column 和 shape。前端不再拼接权威 `cell_id`，只显示后端返回的 ID，并在井、K 单元和粒子起点选择中传回该 ID。

## 质量报告

质量报告分为 `errors`、`warnings` 和 `infos`。阻塞 error 会阻止 `/run-model` 使用该 grid。

当前覆盖：

- 数组 shape；
- NaN/Infinity；
- delr/delc 非正；
- 负厚度；
- 地层面交叉；
- 零厚度和薄层；
- 每层 active/inactive/pinchout 数量；
- 空活动层；
- 无 active cell；
- 孤立 active cell；
- disconnected components；
- 垂向悬空 active cell warning；
- 边界面积、active footprint、覆盖率、边缘相交单元数；
- delr/delc 和有效厚度尺度摘要。

主要稳定错误码包括：

```text
GRID_ARRAY_SHAPE_INVALID
GRID_NONFINITE_VALUE
GRID_NEGATIVE_THICKNESS
GRID_SURFACE_CROSSING
GRID_NO_ACTIVE_CELLS
GRID_EMPTY_LAYER
GRID_ARTIFACT_STALE
GRID_GEOLOGY_CHECKSUM_MISMATCH
GRID_CELL_ID_INVALID
```

## API

```text
POST /projects/<project_id>/grids/validate-config
POST /projects/<project_id>/grids
GET  /projects/<project_id>/grids/active
GET  /projects/<project_id>/grids/<grid_model_id>/summary
GET  /projects/<project_id>/grids/<grid_model_id>/quality
GET  /projects/<project_id>/grids/<grid_model_id>/cells/<cell_id>
GET  /projects/<project_id>/grids/<grid_model_id>/render-data
POST /projects/<project_id>/grids/<grid_model_id>/rebuild
```

`render-data` 返回前端 2D/3D 所需的活动单元、footprint、中心坐标、top/bottom/thickness/idomain 和 `cell_id`。大型网格超过 `MAX_RENDER_CELLS` 时必须按层请求。

## `/run-model` 接入

`/run-model` 当前仍是 legacy flow adapter，但正常请求必须包含：

```json
{
  "project_id": "prj_...",
  "grid_model_id": "grid_..."
}
```

后端从 Grid Store 读取 `delr/delc/top/botm/idomain/x_centers/y_centers`，并拒绝请求中的 `top`、`botm`、`idomain` 或 `grid_arrays` 覆盖。stale grid、quality error、geology checksum mismatch 都会被拒绝。旧 row/column/layer 选择仅通过集中 adapter 临时转换为 `cell_id`，并返回 warning。

## stale 规则

Grid manifest 记录 active geology checksum。地质边界、钻孔、地层、断层或插值参数变化后，当前 active grid 会标记为 `status = stale`，并记录 stale reason。stale grid 可以查看和重建，但不能进入正式运行。

## 前端接入

前端现在把后端 Grid Model 作为正常流程网格来源：

- `GridSettings.vue` 提交 cell size、rotation、minimum thickness 和 boundary overlap；
- `App.vue` 调用 Grid API 创建 grid，保存 `activeGridModelId` 和 quality report；
- `BoundaryMap.vue` 使用后端 `render-data` 的 footprint 画二维网格，点击返回后端 `cell_id`；
- `Real3DViewer.vue` 使用同一 `render-data` 绘制三维网格，点击后按 `cell_id` 获取后端 cell detail；
- `CellDetailPanel.vue` 显示 `cell_id`、layer/row/column、center、top/bottom/thickness、idomain/active，并在运行后显示 head/flows。

## 测试

新增 `backend/tests/test_grid_model.py`，覆盖：

- 配置校验；
- `cell_id` 生成和解析；
- Grid API 创建、active/summary/render/cell detail；
- manifest 和 `.npz` artifact 持久化、checksum 和重启后读取；
- boundary intersection 激活规则；
- quality report 阻塞和 warning；
- geology 更新后 grid stale；
- `/run-model` 必须使用 Grid Store，拒绝覆盖权威数组，并兼容 legacy row/column 选择。
