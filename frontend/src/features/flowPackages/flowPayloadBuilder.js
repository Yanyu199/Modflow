export function buildFlowModelPayload({
  projectId,
  gridModelId,
  currentGridModel,
  gridConfig,
  flowSettings,
  partialParams = {},
  wells = [],
  kCells = [],
  chdCells = [],
  rivCells = []
}) {
  const geometry = currentGridModel && currentGridModel.geometry ? currentGridModel.geometry : {};
  const nlay = Number(geometry.nlay || gridConfig.n_layers || 1);
  const kx = Number(partialParams.kx_default ?? partialParams.k ?? flowSettings.kx_default);
  const ky = Number(partialParams.ky_default ?? partialParams.k ?? flowSettings.ky_default);
  const kz = Number(partialParams.kz_default ?? flowSettings.kz_default);
  const initialHead = Number(partialParams.initial_head_default ?? flowSettings.initial_head_default);
  const icelltype = Number(partialParams.icelltype ?? flowSettings.icelltype);
  const normalizedFlowSettings = {
    initial_head_default: initialHead,
    kx_default: kx,
    ky_default: ky,
    kz_default: kz,
    icelltype
  };
  const kOverrides = kCells
    .filter(cell => cell.cell_id)
    .map(cell => ({ cell_id: cell.cell_id, value: Number(cell.k_val) }));
  return {
    flowSettings: normalizedFlowSettings,
    payload: {
      project_id: projectId,
      grid_model_id: gridModelId,
      simulation: {
        type: 'steady',
        stress_periods: [{ perlen: 1.0, nstp: 1, tsmult: 1.0, steady: true }],
        time_units: 'DAYS'
      },
      initial_conditions: {
        mode: 'default_with_overrides',
        default: initialHead,
        overrides: []
      },
      hydraulic_properties: {
        icelltype: { mode: 'per_layer', values: Array.from({ length: nlay }, () => icelltype) },
        kx: { default: kx, overrides: kOverrides },
        ky: { default: ky, overrides: kOverrides },
        kz: { default: kz, overrides: kOverrides }
      },
      boundaries: {
        chd: chdCells.length > 0 ? [{
          boundary_id: 'selected_chd_cells',
          name: 'Selected CHD cells',
          cells: chdCells
            .filter(cell => cell.cell_id)
            .map(cell => ({ cell_id: cell.cell_id, head: Number(cell.head) }))
        }] : [],
        wel: wells
          .filter(cell => cell.cell_id)
          .map((cell, index) => ({
            well_id: `well_${index + 1}`,
            name: `Well ${index + 1}`,
            cell_id: cell.cell_id,
            rate: Number(cell.rate)
          })),
        riv: rivCells.length > 0 ? [{
          boundary_id: 'selected_riv_cells',
          name: 'Selected RIV cells',
          cells: rivCells
            .filter(cell => cell.cell_id)
            .map(cell => ({
              cell_id: cell.cell_id,
              stage: Number(cell.stage),
              conductance: Number(cell.conductance),
              river_bottom: Number(cell.river_bottom)
            }))
        }] : []
      },
      solver: {
        complexity: 'COMPLEX',
        outer_maximum: 100,
        inner_maximum: 100,
        outer_dvclose: 1.0e-8,
        inner_dvclose: 1.0e-8,
        linear_acceleration: 'BICGSTAB'
      },
      output_control: {
        save_head: true,
        save_budget: true,
        print_budget: true,
        head_file: 'gwf.hds',
        budget_file: 'gwf.bud'
      }
    }
  };
}
