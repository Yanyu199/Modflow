# Project Schema

更新日期：2026-07-12

## 目标

`project_v1` 是当前平台的第一个正式项目定义。它只保存项目上下文和最小引用信息，不保存 UI 折叠状态、当前标签页、服务器绝对路径或运行产物路径。地质体模型、流场模型和运行记录后续需要各自建立独立 schema。

## Schema

```json
{
  "schema_name": "modflow_project",
  "schema_version": "1.0",
  "project_id": "prj_0123456789abcdef",
  "name": "Demo groundwater project",
  "description": "",
  "created_at": "2026-07-12T06:30:00+00:00",
  "modified_at": "2026-07-12T06:30:00+00:00",
  "crs": {
    "authority": "EPSG",
    "code": 32650,
    "wkt": null,
    "axis_order": "xy"
  },
  "units": {
    "horizontal_length": "m",
    "vertical_length": "m",
    "time": "day",
    "flow": "m3/day"
  },
  "model_settings": {
    "model_type": "groundwater_flow",
    "flow_regime": "steady"
  },
  "references": {
    "geology_model_id": null,
    "flow_model_id": null
  },
  "metadata": {}
}
```

## 字段规则

- `schema_name` 固定为 `modflow_project`。
- `schema_version` 当前只支持 `1.0`。未知版本拒绝。
- `project_id` 由后端生成或严格校验，允许字母、数字、下划线和连字符，长度 3-64；`default`、`.`、`..` 被保留。
- `created_at` 和 `modified_at` 必须是带时区的 ISO 8601 时间。
- JSON 不允许 `NaN`、`Infinity`、NumPy 类型、Path 对象或其他非 JSON 类型。
- 顶层未知字段会被拒绝；扩展信息应放入 `metadata`。

## CRS 规则

- CRS 必填。
- 当前支持 `authority="EPSG"` 加合法整数 `code`。
- 可提供 `wkt`；当 EPSG 与 WKT 明显冲突时拒绝。
- `axis_order` 当前只支持 `xy`。
- geographic CRS 不能被静默用于 MODFLOW 网格；例如 EPSG:4326 会被拒绝。
- 当前不实现自动重投影，也不根据文件名或坐标范围猜测 CRS。

## 单位规则

当前 MODFLOW 内部写入仍是 `METERS` 和 `DAYS`，因此首版只接受：

- `horizontal_length`: `m`
- `vertical_length`: `m`
- `time`: `day`
- `flow`: `m3/day`

系统不做静默单位转换。未来支持 `ft`、`m3/s` 或 `L/s` 时，必须显式记录转换来源、目标和转换系数，并增加回归测试。

## API

### `POST /projects/validate`

验证完整项目 JSON，不生成 `project_id`。

### `POST /projects`

创建项目。请求必须包含 `name`、`crs`、`units`、`model_settings`、`references`、`metadata`。如果未提供 `project_id`，后端生成稳定唯一 ID。

成功响应：

```json
{
  "success": true,
  "project": {
    "schema_name": "modflow_project",
    "schema_version": "1.0",
    "project_id": "prj_0123456789abcdef"
  }
}
```

### `GET /projects/<project_id>`

读取项目定义。不存在时返回：

```json
{
  "success": false,
  "error": "项目不存在",
  "code": "project_not_found"
}
```

### `PUT /projects/<project_id>`

更新项目名称、描述、CRS、单位、模型设置、引用或 metadata。`schema_name`、`schema_version`、`project_id` 和 `created_at` 不允许修改。

## 文件存储

项目定义保存到：

```text
backend/projects/<project_id>/project.json
```

目录由后端控制，API 不接受任意路径。写入使用临时文件加 `os.replace` 原子替换，避免半个 JSON 文件。`backend/projects/` 已加入 `.gitignore`，运行时项目不进入代码仓库。

## project_id 生命周期

1. 前端第一次进入时打开“创建工程”对话框。
2. 后端创建项目并返回 `project_id`。
3. Vue 根组件保存唯一 `currentProject`，子组件只接收 `projectId` prop。
4. 边界、钻孔、断层、网格预览、地质模型恢复、源汇项上传和 `/run-model` 都必须显式携带 `project_id`。
5. 缺少 `project_id` 或传入 `default` 会返回验证错误。

## Legacy 兼容

- 新项目导出使用 `modflow_project_bundle`，内部包含 `project` 和 `state`。
- 旧 JSON 不会自动归入 `default`。
- 导入旧 JSON 时，如果当前没有工程，前端要求用户先创建工程并补充 CRS/单位。
- 如果已有当前工程，旧 JSON 只能导入到当前工程上下文，且会提示不会自动猜测 CRS 或单位。

## 当前限制

- `GEO_MODELS` 仍是进程内派生缓存，只按 `project_id` 隔离，不是正式持久化。
- 地质体模型还没有后端 `geology_model_v1` schema。
- 水动力模型配置、运行历史和 run manifest 仍未持久化到项目目录。
- Shapefile 文件本身还没有托管到项目目录，本轮只对上传请求做项目校验。
