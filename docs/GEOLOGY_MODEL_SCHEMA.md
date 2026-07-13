# Geology Model Schema

更新日期：2026-07-12

## 目标

`geology_model` schema v1.0 是当前平台第一个正式地质建模数据契约。它保存可验证、可持久化、可重建地质体所需的标准化输入，不保存 MODFLOW 源汇项、求解器设置、水头结果、budget 结果、UI 折叠状态或服务器绝对路径。

## 顶层结构

```json
{
  "schema_name": "geology_model",
  "schema_version": "1.0",
  "geology_model_id": "geo_0123456789abcdef",
  "project_id": "prj_0123456789abcdef",
  "name": "Site geology model",
  "description": "",
  "created_at": "2026-07-12T08:00:00+00:00",
  "modified_at": "2026-07-12T08:00:00+00:00",
  "spatial_reference": {
    "project_crs_authority": "EPSG",
    "project_crs_code": 32650,
    "axis_order": "xy"
  },
  "units": {
    "horizontal_length": "m",
    "vertical_length": "m"
  },
  "boundary": {},
  "stratigraphy": {
    "formations": []
  },
  "boreholes": [],
  "faults": [],
  "interpolation": {},
  "derived_artifacts": {},
  "diagnostics": {},
  "provenance": {},
  "extensions": {}
}
```

顶层未知字段会被拒绝。JSON 中不允许 `NaN`、`Infinity`、NumPy 类型、Path 对象或其他非 JSON 类型。时间必须是带时区 ISO 8601。

## Project 关联

- `project_id` 必须引用一个已存在的 `modflow_project`。
- geology model 的 CRS 和单位只能从所属项目继承，不能自行覆盖。
- 导入模型声明的 CRS 或单位与项目冲突时拒绝导入，不自动重投影或单位转换。
- 项目已有 active geology model 后，本轮默认拒绝直接修改项目 CRS 或单位。
- 每个项目当前只保存一个 active geology model，项目引用写入 `references.geology_model_id`。

## 边界

边界使用 GeoJSON Feature，几何类型当前支持 `Polygon` 和 `MultiPolygon`。

校验规则：

- geometry 非空，面积大于 0。
- ring 必须闭合。
- 坐标必须是有限 x/y 数值。
- 检查自相交。
- 点数不得超过 `MAX_BOUNDARY_POINTS = 20000`。
- 边界对象不得带 `crs` 字段覆盖项目 CRS。

Shapefile ZIP 上传会读取文件 CRS 并与项目 CRS 比对。缺 CRS 返回 `shapefile_crs_missing`，冲突返回 `project_crs_mismatch`；本轮不自动重投影。

## 钻孔与地层

标准钻孔示例：

```json
{
  "borehole_id": "BH-001",
  "x": 500000.0,
  "y": 3200000.0,
  "collar_elevation": 110.5,
  "total_depth": 45.0,
  "interval_mode": "elevation",
  "intervals": [
    {
      "formation_id": "fm_01",
      "top_elevation": 110.5,
      "bottom_elevation": 98.0
    }
  ],
  "source_ref": "upload:boreholes.csv"
}
```

地层使用稳定 `formation_id`，名称和颜色只用于显示，`kind` 当前只表达地质含义，不自动决定 MODFLOW `icelltype` 或 K。

最低校验包括：

- 钻孔 ID 唯一。
- x/y、高程、深度为有限数。
- `total_depth` 非负。
- intervals 非空。
- 当前仅支持 elevation interval mode。
- `top_elevation` 必须高于 `bottom_elevation`。
- 检查重复或交叉区间。
- interval 引用的 `formation_id` 必须存在。
- 边界外钻孔返回 warning，不静默忽略。
- formation ID 和 order 必须唯一。

`rawCsvContent` 只作为 legacy 迁移输入临时存在。后端计算和重启恢复以标准化 `boreholes` 和 `formations` 为主，不再要求重新解析原始 CSV。

## 断层

断层几何当前支持 `LineString` 和 `MultiLineString`。断层只参与地层插值分块，统一标记：

```json
{
  "hydraulic_role": "geologic_partition_only"
}
```

系统会返回 `FAULT_NOT_HFB` warning，明确它没有进入 MODFLOW HFB 或水力连通计算。

校验规则：

- `fault_id` 唯一。
- 坐标必须为有限 x/y 数值。
- 至少两个不同点。
- 点数不得超过 `MAX_FAULT_POINTS = 5000`。

CSV/Excel 断层上传本身不携带 CRS 元数据，当前按用户声明使用项目 CRS，并写入 provenance。

## 插值与派生结果

插值配置保存在 `interpolation`，默认包括：

- `method = rbf_partitioned_v1`
- `implementation = GeologicalModeler.interpolate_surfaces`
- RBF 函数、fallback、clip margin、最小厚度
- 是否使用断层分块
- 外推和 NoData 策略
- 随机种子

`derived_artifacts` 当前采用可重建策略：保存标准化输入和插值参数，不把大数组无限制写入 JSON。输入或参数变化时，`input_hash` 不匹配会标记为 `status = stale` 并返回 `DERIVED_ARTIFACT_STALE` warning。服务器重启或 `GEO_MODELS` 缓存清空后，可从 `geology_model.json` 重建 `GeologicalModeler`。

## Diagnostics

示例：

```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "summary": {
    "boundary_count": 1,
    "borehole_count": 12,
    "formation_count": 5,
    "fault_count": 2,
    "outside_borehole_count": 0,
    "negative_thickness_count": 0,
    "crossing_interval_count": 0
  }
}
```

错误对象包含稳定 `code`、字段 `path` 和可读 `message`。API 不返回 Python traceback 或服务器绝对路径。

主要错误码包括：

- `PROJECT_NOT_FOUND`
- `PROJECT_CRS_MISMATCH`
- `PROJECT_UNITS_MISMATCH`
- `BOUNDARY_MISSING`
- `BOUNDARY_INVALID`
- `BOUNDARY_SELF_INTERSECTION`
- `BOREHOLE_ID_DUPLICATE`
- `BOREHOLE_COORDINATE_INVALID`
- `BOREHOLE_INTERVAL_EMPTY`
- `BOREHOLE_INTERVAL_OVERLAP`
- `BOREHOLE_NEGATIVE_THICKNESS`
- `FORMATION_UNKNOWN`
- `FORMATION_ORDER_CONFLICT`
- `FAULT_ID_DUPLICATE`
- `FAULT_GEOMETRY_INVALID`
- `SCHEMA_VERSION_UNSUPPORTED`
- `DERIVED_ARTIFACT_STALE`

## API

```text
POST /projects/<project_id>/geology-models/validate
POST /projects/<project_id>/geology-models
GET /projects/<project_id>/geology-models/active
PUT /projects/<project_id>/geology-models/<geology_model_id>
POST /projects/<project_id>/geology-models/<geology_model_id>/rebuild
```

Validate 不持久化，返回 normalized model 和 diagnostics。Create 验证后原子写入并更新 project reference。Get active 可在进程重启后读取标准模型。Update 会重新验证，输入变化后 artifact 标记 stale。Rebuild 从持久化标准输入重建进程内 `GeologicalModeler`，不依赖 raw CSV。

兼容上传接口 `/upload-shapefile`、`/upload-boreholes`、`/upload-faults` 已改为调用统一 geology service：先标准化，再验证，再持久化，再更新可重建缓存。

## 持久化和缓存

文件布局：

```text
backend/projects/<project_id>/
├── project.json
└── geology/
    ├── geology_model.json
    └── artifacts/
```

写入使用临时文件和 `os.replace` 原子替换。API 不接受客户端提供的目录或文件名，也不向前端返回服务器绝对路径。`GEO_MODELS` 只作为可重建缓存，不是权威存储。

## 资源限制

集中配置位于 `backend/geology_limits.py`：

- `MAX_JSON_BYTES = 2 * 1024 * 1024`
- `MAX_ZIP_BYTES = 50 * 1024 * 1024`
- `MAX_JSON_DEPTH = 20`
- `MAX_BOUNDARY_POINTS = 20000`
- `MAX_BOREHOLES = 5000`
- `MAX_INTERVALS_PER_BOREHOLE = 200`
- `MAX_FORMATIONS = 500`
- `MAX_FAULTS = 500`
- `MAX_FAULT_POINTS = 5000`

ZIP 解压检查路径穿越。JSON 请求超过大小限制会返回 `json_request_too_large`。

## 前端导入导出

新工程包格式：

```json
{
  "bundle_schema": "modflow_project_bundle",
  "bundle_version": "1.0",
  "project": {},
  "geology_model": {},
  "state": {}
}
```

导入 geology model 或工程包时，前端先调用后端 validation/create API，只有后端返回 normalized model 后才覆盖当前地质状态。旧 JSON 和旧 `rawCsvContent` 路径仅作为 legacy 迁移入口。

## 升级规则

当前仅支持 `schema_version = "1.0"`。未来版本必须：

- 保留版本号和迁移说明。
- 对未知版本返回稳定错误。
- 明确新增字段的默认值和兼容路径。
- 增加 schema、API、持久化和重建测试。
