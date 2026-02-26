# backend/app.py
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
from geometry_utils import parse_shapefile_zip, extract_xyz_from_zip, parse_zone_shapefile
from modflow_engine import run_simulation, get_grid_geometry
from export_utils import generate_obj_string

app = Flask(__name__)
CORS(app)

# 用于存储上传的地层数据点
LAYER_CACHE = {}


@app.route('/run-model', methods=['POST'])
def run():
    try:
        data = request.json
        boundary = data.get('boundary')
        params = data.get('params')
        custom_boundaries = data.get('boundary_conditions', [])
        wells = data.get('wells', [])
        k_cells = data.get('k_cells', [])
        rch_data = data.get('rch_data', [])
        evt_data = data.get('evt_data', [])

        # 接收粒子追踪起始点
        mp_start_cell = data.get('mp_start_cell')

        if not boundary:
            return jsonify({"error": "Invalid boundary"}), 400

        # 调用引擎
        res_data, logs = run_simulation(
            params=params,
            boundary_coords=boundary,
            custom_boundaries=custom_boundaries,
            layer_cache=LAYER_CACHE,
            wells=wells,
            k_cells=k_cells,
            rch_data=rch_data,
            evt_data=evt_data,
            mp_start_cell=mp_start_cell
        )

        if res_data is None:
            return jsonify({"success": False, "error": "Simulation failed.", "logs": logs})

        # 确保返回 points 和 pathlines
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
        boundary = data.get('boundary')
        params = data.get('params')
        if not boundary: return jsonify({"error": "No boundary"}), 400
        points = get_grid_geometry(params, boundary, LAYER_CACHE)
        return jsonify({"success": True, "points": points})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/upload-layer', methods=['POST'])
def upload_layer():
    try:
        layer_idx = int(request.form.get('layer_index', 0))
        layer_type = request.form.get('type')
        file = request.files['file']
        points = extract_xyz_from_zip(file)
        if layer_idx not in LAYER_CACHE: LAYER_CACHE[layer_idx] = {"top": None, "bottom": None}
        LAYER_CACHE[layer_idx][layer_type] = points
        return jsonify({"success": True, "count": len(points), "layer": layer_idx})
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