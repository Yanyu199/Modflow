export const FLOW_PACKAGE_REGISTRY = Object.freeze({
  CHD: Object.freeze({
    type: 'CHD',
    label: 'Constant Head',
    enabled: true,
    formal: true,
    conflictTypes: ['WEL', 'RIV', 'GHB', 'DRN'],
    fields: Object.freeze([
      { name: 'cell_id', label: 'Cell ID', unit: null, required: true },
      { name: 'head', label: 'Head', unit: 'project length', required: true }
    ])
  }),
  WEL: Object.freeze({
    type: 'WEL',
    label: 'Well',
    enabled: true,
    formal: true,
    conflictTypes: ['CHD', 'RIV', 'GHB', 'DRN'],
    fields: Object.freeze([
      { name: 'cell_id', label: 'Cell ID', unit: null, required: true },
      { name: 'rate', label: 'Rate', unit: 'project flow', required: true }
    ])
  }),
  RIV: Object.freeze({
    type: 'RIV',
    label: 'River',
    enabled: true,
    formal: true,
    conflictTypes: ['CHD', 'WEL', 'GHB', 'DRN'],
    fields: Object.freeze([
      { name: 'cell_id', label: 'Cell ID', unit: null, required: true },
      { name: 'stage', label: 'Stage', unit: 'project length', required: true },
      { name: 'conductance', label: 'Conductance', unit: 'project area / time', required: true },
      { name: 'river_bottom', label: 'River bottom', unit: 'project length', required: true }
    ])
  }),
  GHB: Object.freeze({
    type: 'GHB',
    label: 'General Head Boundary',
    enabled: false,
    formal: false,
    reason: 'Backend package creation is not implemented yet.',
    conflictTypes: ['CHD', 'WEL', 'RIV', 'DRN'],
    fields: Object.freeze([])
  }),
  DRN: Object.freeze({
    type: 'DRN',
    label: 'Drain',
    enabled: false,
    formal: false,
    reason: 'Backend package creation is not implemented yet.',
    conflictTypes: ['CHD', 'WEL', 'RIV', 'GHB'],
    fields: Object.freeze([])
  }),
  RCH: Object.freeze({
    type: 'RCH',
    label: 'Recharge',
    enabled: false,
    formal: false,
    reason: 'Formal Flow Model v1 package is not implemented yet.',
    conflictTypes: [],
    fields: Object.freeze([])
  }),
  EVT: Object.freeze({
    type: 'EVT',
    label: 'Evapotranspiration',
    enabled: false,
    formal: false,
    reason: 'Formal Flow Model v1 package is not implemented yet.',
    conflictTypes: [],
    fields: Object.freeze([])
  })
});

export function listFlowPackages() {
  return Object.values(FLOW_PACKAGE_REGISTRY);
}

export function getFlowPackage(type) {
  return FLOW_PACKAGE_REGISTRY[String(type || '').toUpperCase()] || null;
}

export function enabledFlowPackages() {
  return listFlowPackages().filter(item => item.enabled);
}
