# backend/mf6_wrapper.py
import os
import shutil
import numpy as np
import flopy
from shapely.geometry import LineString, Point

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MF6_EXE_PATH = os.path.join(BASE_DIR, "bin", "mf6.exe")
if not os.path.exists(MF6_EXE_PATH):
    if shutil.which("mf6"): MF6_EXE_PATH = "mf6"

# ⭐ MODPATH 7 路径
MP7_EXE_PATH = r"G:\workspace\flopy-project\modpath7\bin\mpath7.exe"

class MF6Builder:
    def __init__(self, run_id, work_dir):
        self.run_id = run_id
        self.work_dir = work_dir
        self.sim = None
        self.gwf = None

    def initialize_sim(self):
        self.sim = flopy.mf6.MFSimulation(sim_name='sim', exe_name=MF6_EXE_PATH, sim_ws=self.work_dir)
        flopy.mf6.ModflowTdis(self.sim, nper=1, perioddata=[(1.0, 1, 1.0)], time_units='DAYS')
        flopy.mf6.ModflowIms(self.sim, complexity='COMPLEX', outer_maximum=1000, inner_maximum=200)
        self.gwf = flopy.mf6.ModflowGwf(self.sim, modelname='gwf', save_flows=True)

    def setup_dis(self, nlay, nrow, ncol, delr, delc, top, botm, idomain, origin_x, origin_y):
        flopy.mf6.ModflowGwfdis(self.gwf, length_units='METERS', nlay=nlay, nrow=nrow, ncol=ncol,
                                delr=delr, delc=delc, top=top, botm=botm, idomain=idomain,
                                xorigin=origin_x, yorigin=origin_y)

    def setup_npf(self, k_global, k_cells, nlay, nrow, ncol):
        k_array = np.full((nlay, nrow, ncol), float(k_global))
        if k_cells:
            for cell in k_cells:
                r, c, l, v = int(cell['row']), int(cell['col']), cell.get('layer'), float(cell['k_val'])
                if 0 <= r < nrow and 0 <= c < ncol:
                    if l is not None and 0 <= int(l) < nlay: k_array[int(l), r, c] = v
                    else: k_array[:, r, c] = v
        flopy.mf6.ModflowGwfnpf(self.gwf, k=k_array, save_specific_discharge=True, icelltype=1)

    def setup_boundary_conditions(self, active_2d, custom_boundaries, wells, rch_array, evt_array, top_layer, grid_info):
        nrow, ncol = active_2d.shape
        origin_x, origin_y = grid_info['origin_x'], grid_info['origin_y']
        delr, delc = grid_info['delr'], grid_info['delc']
        chd_data, riv_data, drn_data, ghb_data = [], [], [], []
        for b_cfg in custom_boundaries:
            p1, p2 = b_cfg['p1'], b_cfg['p2']
            line = LineString([(p1['x'], p1['y']), (p2['x'], p2['y'])])
            b_type = b_cfg.get('type', 'CHD')
            for i in range(nrow):
                for j in range(ncol):
                    if active_2d[i, j] == 0: continue
                    cx, cy = origin_x + j * delr + delr / 2, origin_y + (nrow - 1 - i) * delc + delc / 2
                    if line.distance(Point(cx, cy)) < (delr + delc) / 4:
                        ratio = line.project(Point(cx, cy)) / line.length if line.length > 0 else 0.0
                        if b_type == 'CHD':
                            chd_data.append([(0, i, j), float(b_cfg.get('head_start', 10)) + (float(b_cfg.get('head_end', 10)) - float(b_cfg.get('head_start', 10))) * ratio])
                        elif b_type == 'RIV':
                            stg = float(b_cfg.get('stage_start', 10)) + (float(b_cfg.get('stage_end', 10)) - float(b_cfg.get('stage_start', 10))) * ratio
                            riv_data.append([(0, i, j), stg, 100, 5])
        if chd_data:
            flopy.mf6.ModflowGwfic(self.gwf, strt=np.mean([x[1] for x in chd_data]))
            flopy.mf6.ModflowGwfchd(self.gwf, stress_period_data={0: chd_data})
        else:
            flopy.mf6.ModflowGwfic(self.gwf, strt=top_layer)
        if riv_data: flopy.mf6.ModflowGwfriv(self.gwf, stress_period_data={0: riv_data})
        wel_spd = [[(int(w.get('layer', 0)), int(w['row']), int(w['col'])), float(w['rate'])] for w in wells]
        if wel_spd: flopy.mf6.ModflowGwfwel(self.gwf, stress_period_data={0: wel_spd})
        if np.any(rch_array > 0): flopy.mf6.ModflowGwfrcha(self.gwf, recharge={0: rch_array})
        if np.any(evt_array > 0): flopy.mf6.ModflowGwfevta(self.gwf, surface=top_layer, rate=evt_array, depth=2.0)
        flopy.mf6.ModflowGwfoc(self.gwf, head_filerecord='gwf.hds', budget_filerecord='gwf.bud', saverecord=[('HEAD', 'ALL'), ('BUDGET', 'ALL')])

    def run(self):
        self.sim.write_simulation()
        return self.sim.run_simulation(silent=True)

    def run_modpath(self, start_points):
        try:
            mp = flopy.modpath.Modpath7(modelname='mp', flowmodel=self.gwf, exe_name=MP7_EXE_PATH, model_ws=self.work_dir)
            pdata = flopy.modpath.ParticleData(start_points, drape=0)
            pg = flopy.modpath.ParticleGroup(particlegroupname='PG1', particledata=pdata)
            flopy.modpath.Modpath7Bas(mp, porosity=0.3)
            flopy.modpath.Modpath7Sim(mp, simulationtype='pathline', trackingdirection='forward', weaksinkoption='pass_through', particlegroups=[pg])
            mp.write_input()
            return mp.run_model(silent=True)
        except Exception as e:
            print(f"MODPATH Error: {e}"); return False, []