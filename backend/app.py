# backend/app.py
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import traceback
import pandas as pd  # 新增 pandas 用于读取断层 Excel/CSV
from geometry_utils import parse_boundary_shapefile_zip, parse_shapefile_zip, parse_zone_shapefile
from modflow_engine import run_simulation, get_grid_geometry
from export_utils import generate_obj_string
from geological_builder import GeologicalModeler
from geology_limits import MAX_JSON_BYTES, MAX_ZIP_BYTES
from geology_model_schema import (
    GeologyModelValidationError,
    boundary_coords_for_frontend,
    linestring_points_for_engine,
    normalized_to_frontend,
)
from geology_model_service import GeologyModelService
from geology_model_store import GeologyModelNotFoundError
from project_schema import ProjectValidationError
from project_store import ProjectConflictError, ProjectNotFoundError, ProjectStore, validate_project_id

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_ZIP_BYTES
CORS(app)

# 受控的进程内派生状态缓存。项目定义持久化在 ProjectStore 中；这里的地质模型缓存可失效。
GEO_MODELS = {}
project_store = ProjectStore()
geology_service = GeologyModelService(project_store)


def api_error(message, status=400, code="validation_error", details=None):
    payload = {"success": False, "error": message, "code": code}
    if details:
        payload["details"] = details
    return jsonify(payload), status


@app.before_request
def reject_oversized_json_request():
    if request.is_json and request.content_length and request.content_length > MAX_JSON_BYTES:
        return api_error(
            f"JSON 请求超过大小限制 {MAX_JSON_BYTES} bytes",
            413,
            "json_request_too_large",
        )


def project_exception_response(exc):
    if isinstance(exc, ProjectNotFoundError):
        return api_error("项目不存在", 404, "project_not_found")
    if isinstance(exc, ProjectConflictError):
        return api_error("项目 ID 已存在", 409, "project_conflict")
    if isinstance(exc, ProjectValidationError):
        return api_error("项目数据无效", 400, "project_validation_error", exc.errors)
    return api_error(str(exc), 400)


def geology_exception_response(exc):
    if isinstance(exc, GeologyModelNotFoundError):
        return api_error("地质模型不存在", 404, "geology_model_not_found")
    if isinstance(exc, GeologyModelValidationError):
        return api_error("地质模型数据无效", 400, "geology_model_validation_error", exc.diagnostics)
    return project_exception_response(exc)


def json_payload():
    return request.get_json(silent=True) or {}


def require_project_id(value):
    if value is None or str(value).strip() == "":
        raise ProjectValidationError("project_id is required")
    return validate_project_id(str(value))


def require_existing_project(project_id):
    project_id = require_project_id(project_id)
    project_store.get(project_id)
    return project_id


def get_existing_project(project_id):
    project_id = require_project_id(project_id)
    return project_store.get(project_id)


def require_project_from_form():
    return require_existing_project(request.form.get("project_id"))


def require_project_from_json(data):
    return require_existing_project(data.get("project_id"))


def truthy_form_value(name):
    value = request.form.get(name)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@app.route('/projects/validate', methods=['POST'])
def validate_project():
    try:
        project = project_store.validate(json_payload())
        return jsonify({"success": True, "project": project})
    except Exception as e:
        return project_exception_response(e)


@app.route('/projects', methods=['POST'])
def create_project():
    try:
        project = project_store.create(json_payload())
        return jsonify({"success": True, "project": project}), 201
    except Exception as e:
        return project_exception_response(e)


@app.route('/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    try:
        project = project_store.get(project_id)
        return jsonify({"success": True, "project": project})
    except Exception as e:
        return project_exception_response(e)


@app.route('/projects/<project_id>', methods=['PUT'])
def update_project(project_id):
    try:
        payload = json_payload()
        existing = project_store.get(project_id)
        if existing.get("references", {}).get("geology_model_id"):
            if ("crs" in payload and payload["crs"] != existing.get("crs")) or (
                "units" in payload and payload["units"] != existing.get("units")
            ):
                return api_error(
                    "项目已有地质模型，当前版本不允许直接修改 CRS 或单位；请先执行未来的迁移流程",
                    409,
                    "project_context_locked_by_geology_model",
                )
        project = project_store.update(project_id, payload)
        return jsonify({"success": True, "project": project})
    except Exception as e:
        return project_exception_response(e)


@app.route('/projects/<project_id>/geology-models/validate', methods=['POST'])
def validate_geology_model(project_id):
    try:
        model = geology_service.validate(project_id, json_payload(), allow_incomplete=False)
        return jsonify({"success": True, "geology_model": model, "diagnostics": model["diagnostics"]})
    except Exception as e:
        return geology_exception_response(e)


@app.route('/projects/<project_id>/geology-models', methods=['POST'])
def create_geology_model(project_id):
    try:
        model = geology_service.create(project_id, json_payload())
        GEO_MODELS[project_id] = geology_service.ensure_cache(project_id, GEO_MODELS)
        return jsonify({
            "success": True,
            "geology_model_id": model["geology_model_id"],
            "geology_model": model,
            "summary": model["diagnostics"]["summary"],
        }), 201
    except Exception as e:
        return geology_exception_response(e)


@app.route('/projects/<project_id>/geology-models/active', methods=['GET'])
def get_active_geology_model(project_id):
    try:
        model = geology_service.get_active(project_id)
        return jsonify({"success": True, "geology_model": model, "diagnostics": model["diagnostics"]})
    except Exception as e:
        return geology_exception_response(e)


@app.route('/projects/<project_id>/geology-models/<geology_model_id>', methods=['PUT'])
def update_geology_model(project_id, geology_model_id):
    try:
        model = geology_service.update(project_id, geology_model_id, json_payload())
        GEO_MODELS.pop(project_id, None)
        if model["diagnostics"]["valid"]:
            GEO_MODELS[project_id] = geology_service.ensure_cache(project_id, GEO_MODELS)
        return jsonify({"success": True, "geology_model": model, "diagnostics": model["diagnostics"]})
    except Exception as e:
        return geology_exception_response(e)


@app.route('/projects/<project_id>/geology-models/<geology_model_id>/rebuild', methods=['POST'])
def rebuild_geology_model(project_id, geology_model_id):
    try:
        model = geology_service.get_active(project_id)
        if model["geology_model_id"] != geology_model_id:
            raise GeologyModelNotFoundError("geology model not found for project")
        model, frontend_data = geology_service.rebuild(project_id, GEO_MODELS)
        return jsonify({
            "success": True,
            "geology_model_id": model["geology_model_id"],
            "diagnostics": model["diagnostics"],
            "frontend": frontend_data,
        })
    except Exception as e:
        return geology_exception_response(e)


@app.route('/upload-boreholes', methods=['POST'])
def upload_boreholes():
    try:
        project_id = require_project_from_form()
        file = request.files['file']

        model = geology_service.update_boreholes_from_upload(project_id, file, cache=GEO_MODELS)
        frontend_data = normalized_to_frontend(model)
        return jsonify({
            "success": True,
            "message": "钻孔数据解析成功",
            "layers_count": frontend_data['layers_count'],
            "layer_mapping": frontend_data['layer_mapping'],  # 传给前端用于真实物理层映射
            "boreholes_count": len(frontend_data['boreholes']),
            "boreholes": frontend_data['boreholes'],
            "geology_model": model,
            "diagnostics": model["diagnostics"],
        })
    except (ProjectValidationError, ProjectNotFoundError, GeologyModelValidationError) as e:
        return geology_exception_response(e)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/upload-faults', methods=['POST'])
def upload_faults():
    try:
        project_id = require_project_from_form()
        file = request.files['file']

        # ⭐ 修改点 1：去掉 .stream，直接将 file 对象传给 pandas，兼容性更好
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.filename.endswith('.xlsx') or file.filename.endswith('.xls'):
            df = pd.read_excel(file)
        else:
            return jsonify({"success": False, "error": "请上传 .csv 或 .xlsx 格式文件"}), 400

        # 智能匹配列名（容错处理：去除表头可能存在的首尾空格）
        df.columns = df.columns.str.strip()

        fault_id_col = '断层编号' if '断层编号' in df.columns else ('Fault_ID' if 'Fault_ID' in df.columns else None)
        x_col = 'X' if 'X' in df.columns else None
        y_col = 'Y' if 'Y' in df.columns else None

        if not fault_id_col or not x_col or not y_col:
            return jsonify({"success": False,
                            "error": f"文件必须包含 '断层编号', 'X', 'Y' 列。当前识别到的列为: {list(df.columns)}"}), 400

        faults_data = []
        # 按断层编号分组，将每一组坐标按行顺序连接成一条断层线
        for fault_id, group in df.groupby(fault_id_col):
            line_coords = []
            for _, row in group.iterrows():
                line_coords.append([float(row[x_col]), float(row[y_col])])

            # 断层线至少需要2个点
            if len(line_coords) >= 2:
                faults_data.append({
                    "fault_id": f"fault_{fault_id}",
                    "name": str(fault_id),
                    "geometry": {"type": "LineString", "coordinates": line_coords},
                    "properties": {"hydraulic_role": "geologic_partition_only"},
                    "source_ref": f"upload:{file.filename}",
                })

        model = geology_service.update_faults(
            project_id,
            faults_data,
            source_metadata={"kind": "csv_or_excel", "crs_source": "user_declared_project_crs"},
            cache=GEO_MODELS,
        )
        frontend_faults = [linestring_points_for_engine(fault) for fault in model["faults"]]

        return jsonify({
            "success": True,
            "message": f"成功解析 {len(frontend_faults)} 条断层线",
            "faults": frontend_faults,
            "geology_model": model,
            "diagnostics": model["diagnostics"],
        })
    except (ProjectValidationError, ProjectNotFoundError, GeologyModelValidationError) as e:
        return geology_exception_response(e)
    except Exception as e:
        # ⭐ 修改点 2：在终端强行打印出详细的错误追踪信息
        print("\n================== 断层文件读取失败 ==================")
        print(traceback.format_exc())
        print("=====================================================\n")
        return jsonify({"success": False, "error": "文件解析失败，请查看后端控制台日志"}), 500


@app.route('/run-model', methods=['POST'])
def run():
    try:
        data = json_payload()
        project_id = require_project_from_json(data)
        boundary = data.get('boundary')
        params = data.get('params')
        custom_boundaries = data.get('boundary_conditions', [])
        wells = data.get('wells', [])
        k_cells = data.get('k_cells', [])
        rch_data = data.get('rch_data', [])
        evt_data = data.get('evt_data', [])
        mp_start_cell = data.get('mp_start_cell')
        faults = data.get('faults', [])  # 获取断层数据

        if not boundary:
            return jsonify({"error": "Invalid boundary"}), 400

        # 获取之前上传钻孔生成的的地质模型
        try:
            geo_model = geology_service.ensure_cache(project_id, GEO_MODELS)
        except Exception:
            return jsonify({"error": "请先上传钻孔数据构建地质模型"}), 400

        # 调用引擎
        res_data, logs = run_simulation(
            params=params,
            boundary_coords=boundary,
            custom_boundaries=custom_boundaries,
            geo_model=geo_model,
            wells=wells,
            k_cells=k_cells,
            rch_data=rch_data,
            evt_data=evt_data,
            mp_start_cell=mp_start_cell,
            faults=faults  # 传递断层数据给引擎
        )

        if res_data is None:
            return jsonify({"success": False, "error": "Simulation failed.", "logs": logs})

        return jsonify({
            "success": True,
            "points": res_data['points'],
            "pathlines": res_data['pathlines'],
            "logs": logs
        })

    except Exception as e:
        print(f"Error in /run-model: {e}")
        if isinstance(e, (ProjectValidationError, ProjectNotFoundError)):
            return project_exception_response(e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/preview-geometry', methods=['POST'])
def preview_geometry():
    try:
        data = json_payload()
        project_id = require_project_from_json(data)
        boundary = data.get('boundary')
        params = data.get('params')
        faults = data.get('faults', [])  # 获取断层数据

        try:
            geo_model = geology_service.ensure_cache(project_id, GEO_MODELS)
        except Exception:
            return jsonify({"error": "请先上传钻孔数据构建地质模型"}), 400

        # 核心逻辑：如果此时前端还没画边界，自动根据钻孔外包络线计算一个默认边界
        if not boundary or len(boundary) < 3:
            xs = [bh['X'] for bh in geo_model.boreholes.values()]
            ys = [bh['Y'] for bh in geo_model.boreholes.values()]
            pad = float(params.get('x_val', 50)) * 2  # 向外扩充两个网格
            boundary = [
                {"x": min(xs) - pad, "y": min(ys) - pad},
                {"x": max(xs) + pad, "y": min(ys) - pad},
                {"x": max(xs) + pad, "y": max(ys) + pad},
                {"x": min(xs) - pad, "y": max(ys) + pad}
            ]

        # 传递断层数据
        points = get_grid_geometry(params, boundary, geo_model, faults)

        return jsonify({
            "success": True,
            "points": points,
            "boundary_auto": boundary,  # 返回自动生成的边界
            "boreholes": geo_model.get_frontend_data()['boreholes'],
            "layer_mapping": geo_model.get_frontend_data()['layer_mapping']  # 带上钻孔以便3D渲染
        })
    except (ProjectValidationError, ProjectNotFoundError) as e:
        return project_exception_response(e)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/upload-shapefile', methods=['POST'])
def upload_shapefile():
    try:
        project_id = require_project_from_form()
        project = get_existing_project(project_id)
        file = request.files['file']
        parsed = parse_boundary_shapefile_zip(file)
        crs = parsed["crs"]
        project_crs = project["crs"]
        source_metadata = dict(parsed["source"] or {})
        if crs is None:
            if not truthy_form_value("assume_project_crs"):
                return api_error("Shapefile 缺少 CRS，当前版本不能静默猜测", 400, "shapefile_crs_missing")
            crs = {
                "authority": project_crs.get("authority"),
                "code": project_crs.get("code"),
                "wkt": project_crs.get("wkt"),
                "axis_order": project_crs.get("axis_order", "xy"),
                "source": "user_confirmed_project_crs",
            }
            source_metadata.update({
                "crs_source": "user_confirmed_project_crs",
                "file_crs_missing": True,
                "declared_project_crs": {
                    "authority": project_crs.get("authority"),
                    "code": project_crs.get("code"),
                    "wkt": project_crs.get("wkt"),
                    "axis_order": project_crs.get("axis_order", "xy"),
                },
            })
        if crs.get("authority") != project_crs.get("authority") or crs.get("code") != project_crs.get("code"):
            return api_error("Shapefile CRS 与项目 CRS 不一致，当前版本不自动重投影", 400, "project_crs_mismatch")
        model = geology_service.update_boundary(project_id, parsed["feature"], source_metadata, cache=GEO_MODELS)
        return jsonify({
            "success": True,
            "data": parsed["coords"],
            "boundary_feature": model["boundary"],
            "shapefile_crs": crs,
            "geology_model": model,
            "diagnostics": model["diagnostics"],
        })
    except (ProjectValidationError, ProjectNotFoundError, GeologyModelValidationError) as e:
        return geology_exception_response(e)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/upload-zone', methods=['POST'])
def upload_zone():
    try:
        require_project_from_form()
        file = request.files['file']
        zones = parse_zone_shapefile(file)
        return jsonify({"success": True, "zones": zones})
    except (ProjectValidationError, ProjectNotFoundError) as e:
        return project_exception_response(e)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/export-model', methods=['POST'])
def export_model():
    try:
        obj_content = generate_obj_string(request.json.get('points', []))
        return Response(obj_content, mimetype="text/plain",
                        headers={"Content-disposition": "attachment; filename=model_export.obj"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
