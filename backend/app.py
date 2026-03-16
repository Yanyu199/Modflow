# backend/app.py
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import pandas as pd
from geometry_utils import parse_shapefile_zip, parse_zone_shapefile
from modflow_engine import run_simulation, get_grid_geometry
from export_utils import generate_obj_string
from geological_builder import GeologicalModeler
app = Flask(__name__)
CORS(app)

# 用于存储全局的三维地质建模对象 (支持多项目/多用户场景可按 project_id 区分)
GEO_MODELS = {}


@app.route('/upload-scatter', methods=['POST'])
def upload_scatter():
    try:
        file = request.files['file']
        filename = file.filename.lower()

        # 支持 CSV 与 Excel
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        else:
            return jsonify({"success": False, "error": "不支持的文件格式，请上传 CSV 或 Excel"}), 400

        # 智能匹配表头（将列名全部转小写进行匹配）
        cols = [str(c).lower().strip() for c in df.columns]

        x_col = next((c for c in cols if c in ['x', 'lon', '经度', 'x坐标']), None)
        y_col = next((c for c in cols if c in ['y', 'lat', '纬度', 'y坐标']), None)
        val_col = next((c for c in cols if c in ['value', 'val', 'rate', '入渗率', '蒸发率', '数值', 'v']), None)

        if not (x_col and y_col and val_col):
            return jsonify({"success": False,
                            "error": f"缺少必需列，当前识别到的列有: {', '.join(df.columns)}。请确保包含 X, Y, Value 列"}), 400

        # 提取目标列并剔除空值
        df.columns = cols
        df_clean = df[[x_col, y_col, val_col]].dropna()

        # 转换为前端所需结构
        result = []
        for _, row in df_clean.iterrows():
            result.append({
                "x": float(row[x_col]),
                "y": float(row[y_col]),
                "value": float(row[val_col])
            })

        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
@app.route('/upload-boreholes', methods=['POST'])
def upload_boreholes():
    try:
        project_id = request.form.get('project_id', 'default')
        file = request.files['file']

        geo_model = GeologicalModeler(file.stream)
        geo_model.preprocess_data()
        GEO_MODELS[project_id] = geo_model

        frontend_data = geo_model.get_frontend_data()

        return jsonify({
            "success": True,
            "message": "钻孔数据解析成功",
            "layers_count": frontend_data['layers_count'],
            "layer_mapping": frontend_data['layer_mapping'],  # 传给前端用于真实物理层映射
            "boreholes_count": len(geo_model.boreholes),
            "boreholes": frontend_data['boreholes']
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/run-model', methods=['POST'])
def run():
    try:
        data = request.json
        project_id = data.get('project_id', 'default')
        boundary = data.get('boundary')
        params = data.get('params')
        custom_boundaries = data.get('boundary_conditions', [])
        wells = data.get('wells', [])
        k_cells = data.get('k_cells', [])
        rch_data = data.get('rch_data', [])
        evt_data = data.get('evt_data', [])
        mp_start_cell = data.get('mp_start_cell')

        if not boundary:
            return jsonify({"error": "Invalid boundary"}), 400

        # 获取之前上传钻孔生成的的地质模型
        geo_model = GEO_MODELS.get(project_id)
        if not geo_model:
            return jsonify({"error": "请先上传钻孔数据构建地质模型"}), 400

        # 调用引擎
        res_data, logs = run_simulation(
            params=params,
            boundary_coords=boundary,
            custom_boundaries=custom_boundaries,
            geo_model=geo_model,  # 将字典换成了模型对象
            wells=wells,
            k_cells=k_cells,
            rch_data=rch_data,
            evt_data=evt_data,
            mp_start_cell=mp_start_cell
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
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/preview-geometry', methods=['POST'])
def preview_geometry():
    try:
        data = request.json
        project_id = data.get('project_id', 'default')
        boundary = data.get('boundary')
        params = data.get('params')

        geo_model = GEO_MODELS.get(project_id)
        if not geo_model:
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

        points = get_grid_geometry(params, boundary, geo_model)

        return jsonify({
            "success": True,
            "points": points,
            "boundary_auto": boundary,  # 返回自动生成的边界
            "boreholes": geo_model.get_frontend_data()['boreholes'],
            "layer_mapping": geo_model.get_frontend_data()['layer_mapping']# 带上钻孔以便3D渲染
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/upload-shapefile', methods=['POST'])
def upload_shapefile():
    try:
        file = request.files['file']
        coords = parse_shapefile_zip(file)
        return jsonify({"success": True, "data": coords})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/upload-zone', methods=['POST'])
def upload_zone():
    try:
        file = request.files['file']
        zones = parse_zone_shapefile(file)
        return jsonify({"success": True, "zones": zones})
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