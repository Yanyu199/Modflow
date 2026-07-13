import copy

from geology_model_schema import generate_geology_model_id, project_geology_units, project_spatial_reference


def boundary_feature(size=100.0):
    return {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [0.0, 0.0],
                    [size, 0.0],
                    [size, size],
                    [0.0, size],
                    [0.0, 0.0],
                ]
            ],
        },
    }


def formations():
    return [
        {
            "formation_id": "fm_01",
            "name": "Aquifer 1",
            "order": 1,
            "kind": "aquifer",
            "allow_missing": False,
            "allow_pinchout": False,
            "display": {"color": "#9ecae1"},
            "source_layer_id": 1,
        },
        {
            "formation_id": "fm_02",
            "name": "Aquitard 1",
            "order": 2,
            "kind": "aquitard",
            "allow_missing": False,
            "allow_pinchout": False,
            "display": {"color": "#fdd0a2"},
            "source_layer_id": 2,
        },
    ]


def borehole(borehole_id="BH-001", x=25.0, y=25.0):
    return {
        "borehole_id": borehole_id,
        "x": x,
        "y": y,
        "collar_elevation": 110.0,
        "total_depth": 30.0,
        "interval_mode": "elevation",
        "intervals": [
            {"formation_id": "fm_01", "top_elevation": 110.0, "bottom_elevation": 95.0},
            {"formation_id": "fm_02", "top_elevation": 95.0, "bottom_elevation": 80.0},
        ],
        "source_ref": "test:standardized",
    }


def fault(fault_id="fault_01"):
    return {
        "fault_id": fault_id,
        "name": "Fault 1",
        "geometry": {
            "type": "LineString",
            "coordinates": [[10.0, 10.0], [90.0, 90.0]],
        },
        "properties": {"hydraulic_role": "geologic_partition_only"},
        "source_ref": "test:standardized",
    }


def valid_geology_model(project, include_fault=True):
    model = {
        "schema_name": "geology_model",
        "schema_version": "1.0",
        "geology_model_id": generate_geology_model_id(),
        "project_id": project["project_id"],
        "name": "Test geology model",
        "description": "",
        "spatial_reference": project_spatial_reference(project),
        "units": project_geology_units(project),
        "boundary": boundary_feature(),
        "stratigraphy": {"formations": formations()},
        "boreholes": [borehole()],
        "faults": [fault()] if include_fault else [],
        "interpolation": {
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
        },
        "derived_artifacts": {},
        "diagnostics": {},
        "provenance": {"source": "pytest"},
        "extensions": {},
    }
    return copy.deepcopy(model)


def with_model_change(model, mutator):
    changed = copy.deepcopy(model)
    mutator(changed)
    return changed
