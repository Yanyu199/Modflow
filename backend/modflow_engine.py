# backend/modflow_engine.py
import os, shutil, uuid, traceback, numpy as np
from geometry_tools import generate_grid_info, compute_layer_elevations, map_zones_to_grid
from mf6_wrapper import MF6Builder, BASE_DIR
from post_process import process_results, process_pathlines

def run_simulation(params, boundary_coords, custom_boundaries=[], layer_cache={}, wells=[], k_cells=[], rch_data=[], evt_data=[], mp_start_cell=None):
    run_id = str(uuid.uuid4())[:8]
    WORK_DIR = os.path.join(BASE_DIR, "workspace", run_id)
    logs = []
    os.makedirs(WORK_DIR, exist_ok=True)
    try:
        logs.append(f"🚀 Starting Simulation [{run_id}]...")
        grid = generate_grid_info(params, boundary_coords)
        nlay = int(params.get("n_layers", 1))
        top_arrays, bot_arrays = compute_layer_elevations(nlay, grid['nrow'], grid['ncol'], layer_cache, grid['grid_x'], grid['grid_y'], float(params.get("z_thick", 10.0)))
        idomain = np.zeros((nlay, grid['nrow'], grid['ncol']), dtype=int)
        for k in range(nlay): idomain[k, :, :] = grid['active_2d']

        rch_arr = map_zones_to_grid(rch_data, grid['nrow'], grid['ncol'], grid['active_2d'], grid['grid_centers'])
        evt_arr = map_zones_to_grid(evt_data, grid['nrow'], grid['ncol'], grid['active_2d'], grid['grid_centers'])

        builder = MF6Builder(run_id, WORK_DIR)
        builder.initialize_sim()
        builder.setup_dis(nlay, grid['nrow'], grid['ncol'], grid['delr'], grid['delc'], top_arrays[0], bot_arrays, idomain, grid['origin_x'], grid['origin_y'])
        builder.setup_npf(params.get("k", 10.0), k_cells, nlay, grid['nrow'], grid['ncol'])
        builder.setup_boundary_conditions(grid['active_2d'], custom_boundaries, wells, rch_arr, evt_arr, top_arrays[0], grid)

        success, buff = builder.run()
        logs.append("\n".join(buff) if buff else "No output from MF6.")
        if not success: return None, "\n".join(logs)

        pathlines = []
        if mp_start_cell:
            logs.append("Step 5: Running MODPATH...")
            start_pts = [(int(mp_start_cell['layer']), int(mp_start_cell['row']), int(mp_start_cell['col']))]
            if builder.run_modpath(start_pts):
                pathlines = process_pathlines(WORK_DIR, grid)

        points = process_results(WORK_DIR, nlay, grid['nrow'], grid['ncol'], idomain, top_arrays, bot_arrays, grid)
        return {"points": points, "pathlines": pathlines}, "\n".join(logs)
    except Exception as e:
        return None, f"❌ System Error: {str(e)}\n{traceback.format_exc()}"
    finally:
        if os.path.exists(WORK_DIR): shutil.rmtree(WORK_DIR)

def get_grid_geometry(params, boundary_coords, layer_cache={}):
    try:
        grid = generate_grid_info(params, boundary_coords)
        nlay = int(params.get("n_layers", 1))
        top, bot = compute_layer_elevations(nlay, grid['nrow'], grid['ncol'], layer_cache, grid['grid_x'], grid['grid_y'], float(params.get("z_thick", 10.0)))
        points = []
        for k in range(nlay):
            for i in range(grid['nrow']):
                for j in range(grid['ncol']):
                    if grid['active_2d'][i, j] == 1:
                        points.append({"x": grid['origin_x'] + j * grid['delr'] + grid['delr'] / 2, "y": grid['origin_y'] + (grid['nrow'] - 1 - i) * grid['delc'] + grid['delc'] / 2, "layer": k, "row": i, "col": j, "top": float(top[k][i, j]), "bottom": float(bot[k][i, j]), "head": None, "flows": None})
        return points
    except Exception as e: raise e