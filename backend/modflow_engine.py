# backend/modflow_engine.py
import os, shutil, uuid, traceback, numpy as np
from geometry_tools import generate_grid_info, map_zones_to_grid  # 移除了 compute_layer_elevations
from mf6_wrapper import MF6Builder, BASE_DIR
from post_process import process_results, process_pathlines


def run_simulation(params, boundary_coords, custom_boundaries=[], geo_model=None, wells=[], k_cells=[], rch_data=[],
                   evt_data=[], mp_start_cell=None):
    run_id = str(uuid.uuid4())[:8]
    WORK_DIR = os.path.join(BASE_DIR, "workspace", run_id)
    logs = []
    os.makedirs(WORK_DIR, exist_ok=True)
    try:
        logs.append(f"🚀 Starting Simulation [{run_id}]...")
        grid = generate_grid_info(params, boundary_coords)

        if geo_model is None:
            return None, "❌ 未提供有效的钻孔地层模型数据"

        logs.append("⏳ 正在进行三维地层插值与尖灭拓扑计算...")
        # 传入计算好的 X, Y 网格坐标矩阵，获取插值后的高程字典
        surfaces = geo_model.interpolate_surfaces(grid['grid_x'], grid['grid_y'])
        nlay = len(geo_model.layers)

        top_arrays = []
        bot_arrays = []

        for layer_id in geo_model.layers:
            top_arrays.append(surfaces[layer_id]['Top'])
            bot_arrays.append(surfaces[layer_id]['Bottom'])

        # Flopy MF6 格式要求：top 是顶板 2D 数组，botm 是各层底板组成的 3D 数组
        mf_top = top_arrays[0]
        mf_botm = np.stack(bot_arrays, axis=0)

        idomain = np.zeros((nlay, grid['nrow'], grid['ncol']), dtype=int)
        for k in range(nlay): idomain[k, :, :] = grid['active_2d']

        rch_arr = map_zones_to_grid(rch_data, grid['nrow'], grid['ncol'], grid['active_2d'], grid['grid_centers'])
        evt_arr = map_zones_to_grid(evt_data, grid['nrow'], grid['ncol'], grid['active_2d'], grid['grid_centers'])

        builder = MF6Builder(run_id, WORK_DIR)
        builder.initialize_sim()

        # 传入新的 mf_top 和 mf_botm
        builder.setup_dis(nlay, grid['nrow'], grid['ncol'], grid['delr'], grid['delc'], mf_top, mf_botm, idomain,
                          grid['origin_x'], grid['origin_y'])
        builder.setup_npf(params.get("k", 10.0), k_cells, nlay, grid['nrow'], grid['ncol'])
        builder.setup_boundary_conditions(grid['active_2d'], custom_boundaries, wells, rch_arr, evt_arr, mf_top, grid)

        success, buff = builder.run()

        if success:
            logs.append("✅ MF6 引擎计算顺利完成！")
            if buff:
                logs.append("\n".join(buff))
        else:
            logs.append("❌ MF6 引擎在解算矩阵时发生致命崩溃！")
            if buff:
                logs.append("\n--- 🖥️ 引擎控制台输出 ---")
                logs.append("\n".join(buff))
            else:
                logs.append("\n--- 🖥️ 引擎无控制台输出 (发生闪退) ---")

            # ⭐ 强行读取底层 Fortran 生成的 .lst 诊断日志寻找真凶
            lst_file_gwf = os.path.join(WORK_DIR, "gwf.lst")
            lst_file_sim = os.path.join(WORK_DIR, "mfsim.lst")

            error_details = []
            for target_lst in [lst_file_gwf, lst_file_sim]:
                if os.path.exists(target_lst):
                    error_details.append(f"\n--- 📄 提取底层日志: {os.path.basename(target_lst)} (最后 30 行) ---")
                    try:
                        with open(target_lst, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            error_details.extend([line.strip() for line in lines[-30:]])
                    except Exception as e:
                        error_details.append(f"读取日志文件失败: {e}")

            if error_details:
                logs.extend(error_details)
            else:
                logs.append("\n⚠️ 未找到任何 .lst 日志文件，引擎在极早期预处理阶段就崩溃了。")

            # ⭐ 追加智能原因分析与排查建议
            logs.append("\n========================================")
            logs.append("💡 【系统智能原因分析与排查建议】")
            logs.append("========================================")
            logs.append("出现此崩溃通常是因为【物理水文参数】与【三维地质几何】发生严重冲突，请检查：")
            logs.append(
                "1. 【干涸崩溃】：如果日志提到 'Failed to solve' 或 'Outer iteration convergence failure'，通常是因为某处含水层被抽干。")
            logs.append("   👉 建议：检查是否有【抽水井(Well)】的抽水量设置得过大(-1000等)，导致局部网格瞬间干涸。")
            logs.append("2. 【边界马桶效应】：边界水头设定是否远低于该处的地层标高？")
            logs.append(
                "   👉 建议：如果钻孔地表在 100米，定水头(CHD)请勿设为 10米，否则水会瞬间泄光。请将其设为接近 100 的数值。")
            logs.append("3. 【渗透系数(K)异常】：K 值是否太小 (如 1e-10) 或相邻层差异过大？")
            logs.append("   👉 建议：将左侧参数面板的渗透系数适当调大（如 10.0）再试。")
            logs.append("4. 【极端几何扭曲】：是否有钻孔之间的厚度变化极其剧烈（如 0.1m 骤变到 50m）？")
            logs.append("   👉 建议：如果确信是地层极薄导致，这是数值计算的物理极限，建议适当减小XY剖分密度。")

            return None, "\n".join(logs)

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


def get_grid_geometry(params, boundary_coords, geo_model=None):
    try:
        grid = generate_grid_info(params, boundary_coords)
        if geo_model is None:
            raise Exception("未提供地层模型数据")

        surfaces = geo_model.interpolate_surfaces(grid['grid_x'], grid['grid_y'])
        nlay = len(geo_model.layers)

        points = []
        for k, layer_id in enumerate(geo_model.layers):
            top_arr = surfaces[layer_id]['Top']
            bot_arr = surfaces[layer_id]['Bottom']
            for i in range(grid['nrow']):
                for j in range(grid['ncol']):
                    if grid['active_2d'][i, j] == 1:
                        points.append({
                            "x": grid['origin_x'] + j * grid['delr'] + grid['delr'] / 2,
                            "y": grid['origin_y'] + (grid['nrow'] - 1 - i) * grid['delc'] + grid['delc'] / 2,
                            "layer": k,
                            "row": i,
                            "col": j,
                            "top": float(top_arr[i, j]),
                            "bottom": float(bot_arr[i, j]),
                            "head": None,
                            "flows": None
                        })
        return points
    except Exception as e:
        raise e