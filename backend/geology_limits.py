MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_JSON_DEPTH = 20

MAX_BOUNDARY_POINTS = 20000
MAX_BOREHOLES = 5000
MAX_INTERVALS_PER_BOREHOLE = 200
MAX_FORMATIONS = 500
MAX_FAULTS = 500
MAX_FAULT_POINTS = 5000

SUPPORTED_BOUNDARY_TYPES = {"Polygon", "MultiPolygon"}
SUPPORTED_FAULT_TYPES = {"LineString", "MultiLineString"}
SUPPORTED_FORMATION_KINDS = {"aquifer", "aquitard", "unknown"}

DEFAULT_INTERPOLATION = {
    "method": "rbf_partitioned_v1",
    "implementation": "GeologicalModeler.interpolate_surfaces",
    "parameters": {
        "rbf_function": "thin_plate",
        "fallback": "nearest",
        "clip_margin": 5.0,
        "minimum_thickness": 0.1,
    },
    "use_fault_partitions": True,
    "extrapolation": "nearest",
    "nodata": "fill_with_layer_mean",
    "random_seed": None,
}
