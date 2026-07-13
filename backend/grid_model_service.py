import copy
import math

import numpy as np
from shapely.affinity import rotate as shp_rotate
from shapely.geometry import MultiPolygon, Point, Polygon, shape
from shapely.ops import unary_union

from geological_builder import GeologicalModeler
from geology_model_schema import (
    GeologyModelValidationError,
    linestring_points_for_engine,
    stable_hash,
)
from geology_model_service import build_geological_modeler_from_geology_model
from geology_model_store import GeologyModelNotFoundError, GeologyModelStore
from grid_model_schema import (
    GRID_TYPE,
    MAX_NCOL,
    MAX_NLAY,
    MAX_NROW,
    MAX_RENDER_CELLS,
    MAX_TOTAL_CELLS,
    GridModelNotFoundError,
    GridModelValidationError,
    cell_id,
    dependency_versions,
    generate_grid_model_id,
    grid_item,
    parse_cell_id,
    quality_report,
    stable_hash as grid_hash,
    validate_grid_config,
)
from grid_model_store import GridArtifactError, GridModelStore
from project_schema import ProjectValidationError, now_iso


def geology_checksum(model):
    return stable_hash(
        {
            "geology_model_id": model.get("geology_model_id"),
            "boundary": model.get("boundary"),
            "formations": (model.get("stratigraphy") or {}).get("formations", []),
            "boreholes": model.get("boreholes", []),
            "faults": model.get("faults", []),
            "interpolation": model.get("interpolation", {}),
            "derived_artifacts": model.get("derived_artifacts", {}),
        }
    )


def _rotation_radians(rotation_degrees):
    return math.radians(float(rotation_degrees or 0.0))


def rotate_xy(x, y, rotation_degrees):
    theta = _rotation_radians(rotation_degrees)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    return x * cos_t - y * sin_t, x * sin_t + y * cos_t


def inverse_rotate_xy(x, y, rotation_degrees):
    return rotate_xy(x, y, -rotation_degrees)


def local_cell_corners(xorigin, yorigin, delr, delc, nrow, row, col):
    x0 = xorigin + float(np.sum(delr[:col]))
    x1 = x0 + float(delr[col])
    y_top = yorigin + float(np.sum(delc)) - float(np.sum(delc[:row]))
    y_bottom = y_top - float(delc[row])
    return [(x0, y_bottom), (x1, y_bottom), (x1, y_top), (x0, y_top)]


def world_cell_polygon(xorigin, yorigin, delr, delc, nrow, row, col, rotation):
    corners = [rotate_xy(x, y, rotation) for x, y in local_cell_corners(xorigin, yorigin, delr, delc, nrow, row, col)]
    return Polygon(corners)


def cell_center_xy(xorigin, yorigin, delr, delc, nrow, row, col, rotation):
    local_x = xorigin + float(np.sum(delr[:col])) + float(delr[col]) / 2.0
    local_y = yorigin + float(np.sum(delc)) - float(np.sum(delc[:row])) - float(delc[row]) / 2.0
    return rotate_xy(local_x, local_y, rotation)


def grid_bounds_from_boundary(boundary_geom, rotation):
    rotated = shp_rotate(boundary_geom, -rotation, origin=(0, 0), use_radians=False)
    return rotated.bounds


def build_quality_report(manifest, arrays, boundary_geom=None, cell_polygons=None):
    errors, warnings, infos = [], [], []
    geometry = manifest["geometry"]
    nlay, nrow, ncol = geometry["nlay"], geometry["nrow"], geometry["ncol"]
    delr = np.asarray(arrays["delr"], dtype=float)
    delc = np.asarray(arrays["delc"], dtype=float)
    top = np.asarray(arrays["top"], dtype=float)
    botm = np.asarray(arrays["botm"], dtype=float)
    idomain = np.asarray(arrays["idomain"], dtype=int)
    min_thick = float(manifest["generation"]["minimum_thickness"])

    summary = {
        "nlay": nlay,
        "nrow": nrow,
        "ncol": ncol,
        "total_cells": int(nlay * nrow * ncol),
        "per_layer": [],
        "pinchout_total": 0,
        "active_cell_count": int(np.count_nonzero(idomain == 1)) if idomain.shape == (nlay, nrow, ncol) else 0,
    }

    expected_shapes = {
        "delr": (ncol,),
        "delc": (nrow,),
        "top": (nrow, ncol),
        "botm": (nlay, nrow, ncol),
        "idomain": (nlay, nrow, ncol),
    }
    for name, expected in expected_shapes.items():
        if np.asarray(arrays[name]).shape != expected:
            errors.append(grid_item("error", "GRID_ARRAY_SHAPE_INVALID", name, f"{name} shape must be {expected}"))
    if errors:
        return quality_report(errors, warnings, infos, summary)

    for name in ("delr", "delc", "top", "botm"):
        if not np.all(np.isfinite(arrays[name])):
            errors.append(grid_item("error", "GRID_NONFINITE_VALUE", name, f"{name} contains NaN or Infinity"))
    if np.any(delr <= 0) or np.any(delc <= 0):
        errors.append(grid_item("error", "GRID_ARRAY_SHAPE_INVALID", "delr/delc", "delr and delc must be positive"))

    layer_tops = np.empty_like(botm, dtype=float)
    layer_tops[0] = top
    if nlay > 1:
        layer_tops[1:] = botm[:-1]
    thickness = layer_tops - botm
    if not np.all(np.isfinite(thickness)):
        errors.append(grid_item("error", "GRID_NONFINITE_VALUE", "thickness", "thickness contains NaN or Infinity"))
    negative_count = int(np.count_nonzero(thickness < 0.0))
    zero_count = int(np.count_nonzero(np.isclose(thickness, 0.0)))
    thin_count = int(np.count_nonzero((thickness >= 0.0) & (thickness < min_thick)))
    if negative_count:
        errors.append(grid_item("error", "GRID_NEGATIVE_THICKNESS", "botm", "Layer bottom is above layer top", count=negative_count))
        errors.append(grid_item("error", "GRID_SURFACE_CROSSING", "botm", "Adjacent geologic surfaces cross", count=negative_count))
    if zero_count:
        warnings.append(grid_item("warning", "GRID_ZERO_THICKNESS", "thickness", "Zero-thickness cells were deactivated", count=zero_count))
    if thin_count:
        warnings.append(grid_item("warning", "GRID_THIN_CELL", "thickness", "Cells below minimum thickness were deactivated", count=thin_count))

    for k in range(nlay):
        active = int(np.count_nonzero(idomain[k] == 1))
        inactive = int(nrow * ncol - active)
        pinchout = int(np.count_nonzero((thickness[k] >= 0.0) & (thickness[k] < min_thick)))
        summary["pinchout_total"] += pinchout
        layer_summary = {
            "layer": k,
            "active": active,
            "inactive": inactive,
            "pinchout": pinchout,
        }
        comps, isolated = connected_components(idomain[k] == 1)
        layer_summary["active_components"] = comps
        layer_summary["isolated_active_cells"] = isolated
        if active == 0:
            errors.append(grid_item("error", "GRID_EMPTY_LAYER", f"idomain[{k}]", "Layer has no active cells", layer=k))
        if isolated:
            warnings.append(grid_item("warning", "GRID_ISOLATED_CELL", f"idomain[{k}]", "Layer has isolated active cells", layer=k, count=isolated))
        if comps > 1:
            warnings.append(grid_item("warning", "GRID_DISCONNECTED_COMPONENTS", f"idomain[{k}]", "Layer has disconnected active components", layer=k, count=comps))
        summary["per_layer"].append(layer_summary)

    if summary["active_cell_count"] == 0:
        errors.append(grid_item("error", "GRID_NO_ACTIVE_CELLS", "idomain", "Grid contains no active cells"))

    if nlay > 1:
        dangling = 0
        for k in range(1, nlay):
            dangling += int(np.count_nonzero((idomain[k] == 1) & (idomain[k - 1] == 0)))
        if dangling:
            warnings.append(grid_item("warning", "GRID_VERTICAL_DISCONNECT", "idomain", "Active lower cells are disconnected from inactive cells above", count=dangling))
        summary["vertical_dangling_active_cells"] = dangling

    if boundary_geom is not None and cell_polygons is not None:
        active_2d = np.any(idomain == 1, axis=0)
        active_polys = [cell_polygons[(i, j)] for i in range(nrow) for j in range(ncol) if active_2d[i, j]]
        active_union = unary_union(active_polys) if active_polys else Polygon()
        boundary_area = float(boundary_geom.area)
        active_area = float(active_union.area) if not active_union.is_empty else 0.0
        covered_area = float(active_union.intersection(boundary_geom).area) if boundary_area > 0 and not active_union.is_empty else 0.0
        outside_area = float(active_union.difference(boundary_geom).area) if not active_union.is_empty else 0.0
        coverage_ratio = covered_area / boundary_area if boundary_area > 0 else 0.0
        edge_count = 0
        for i in range(nrow):
            for j in range(ncol):
                poly = cell_polygons[(i, j)]
                inter_area = poly.intersection(boundary_geom).area
                if inter_area > 0 and inter_area < poly.area:
                    edge_count += 1
        summary["boundary"] = {
            "boundary_area": boundary_area,
            "active_cell_footprint_area": active_area,
            "covered_boundary_area": covered_area,
            "coverage_ratio": coverage_ratio,
            "outside_active_area": outside_area,
            "edge_intersection_cell_count": edge_count,
        }
        if coverage_ratio < 0.5:
            warnings.append(grid_item("warning", "GRID_BOUNDARY_COVERAGE_LOW", "boundary", "Active grid coverage is low", coverage_ratio=coverage_ratio))

    valid_thickness = thickness[(idomain == 1) & np.isfinite(thickness)]
    summary["scale"] = {
        "min_delr": float(np.min(delr)) if delr.size else None,
        "max_delr": float(np.max(delr)) if delr.size else None,
        "min_delc": float(np.min(delc)) if delc.size else None,
        "max_delc": float(np.max(delc)) if delc.size else None,
        "min_active_thickness": float(np.min(valid_thickness)) if valid_thickness.size else None,
        "max_active_thickness": float(np.max(valid_thickness)) if valid_thickness.size else None,
        "plan_aspect_ratio": float(max(np.max(delr), np.max(delc)) / min(np.min(delr), np.min(delc))) if delr.size and delc.size else None,
    }
    return quality_report(errors, warnings, infos, summary)


def connected_components(mask):
    nrow, ncol = mask.shape
    visited = np.zeros(mask.shape, dtype=bool)
    components = 0
    isolated = 0
    for i in range(nrow):
        for j in range(ncol):
            if not mask[i, j] or visited[i, j]:
                continue
            components += 1
            stack = [(i, j)]
            visited[i, j] = True
            count = 0
            while stack:
                r, c = stack.pop()
                count += 1
                for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                    if 0 <= rr < nrow and 0 <= cc < ncol and mask[rr, cc] and not visited[rr, cc]:
                        visited[rr, cc] = True
                        stack.append((rr, cc))
            if count == 1:
                isolated += 1
    return components, isolated


class GridModelService:
    def __init__(self, project_store, geology_store=None, grid_store=None):
        self.project_store = project_store
        self.geology_store = geology_store or GeologyModelStore(project_store)
        self.grid_store = grid_store or GridModelStore(project_store)

    def _project(self, project_id):
        return self.project_store.get(project_id)

    def validate_config(self, project_id, payload):
        self._project(project_id)
        config = validate_grid_config(payload)
        return {"success": True, "config": config}

    def create(self, project_id, payload):
        project = self._project(project_id)
        config = validate_grid_config(payload)
        geology_model = self.geology_store.get_active(project)
        self._validate_geology_for_grid(geology_model)
        arrays, geometry, quality, cell_polygons = self._generate_arrays(geology_model, config)
        grid_model_id = generate_grid_model_id()
        now = now_iso()
        manifest = {
            "schema_name": "grid_model",
            "schema_version": "1.0",
            "grid_model_id": grid_model_id,
            "project_id": project_id,
            "geology_model_id": geology_model["geology_model_id"],
            "name": "Structured groundwater grid",
            "created_at": now,
            "modified_at": now,
            "grid_type": GRID_TYPE,
            "status": "ready" if quality["valid"] else "invalid",
            "generation": {
                **config,
                "index_base": 0,
                "cell_id_format": "<grid_model_id>:L<layer>:R<row>:C<column>",
            },
            "geometry": geometry,
            "artifacts": {},
            "quality": quality,
            "provenance": {
                "application": "flopy-project",
                "schema_created_by": "backend.grid_model_service",
                "geology_checksum": geology_checksum(geology_model),
                "geology_input_hash": geology_model.get("derived_artifacts", {}).get("input_hash"),
                "artifact_checksum": None,
                "dependencies": dependency_versions(),
            },
        }
        manifest["provenance"]["artifact_checksum"] = grid_hash(
            {
                "geometry": manifest["geometry"],
                "generation": manifest["generation"],
                "quality_summary": quality["summary"],
            }
        )
        saved = self.grid_store.save(project, manifest, arrays)
        self.project_store.update(
            project_id,
            {
                "references": {
                    "geology_model_id": project["references"].get("geology_model_id"),
                    "grid_model_id": saved["grid_model_id"],
                    "flow_model_id": project["references"].get("flow_model_id"),
                }
            },
        )
        try:
            from flow_model_schema import FlowModelNotFoundError
            from flow_model_store import FlowModelStore

            FlowModelStore(self.project_store).mark_active_stale(
                project,
                "Grid model was regenerated; re-check and save the flow model before running.",
            )
        except FlowModelNotFoundError:
            pass
        return saved

    def get_active(self, project_id):
        project = self._project(project_id)
        return self.grid_store.get_active(project)

    def summary(self, project_id, grid_model_id):
        manifest = self._manifest(project_id, grid_model_id)
        return {
            "grid_model_id": manifest["grid_model_id"],
            "status": manifest.get("status"),
            "geometry": manifest["geometry"],
            "generation": manifest["generation"],
            "quality_summary": manifest.get("quality", {}).get("summary", {}),
        }

    def quality(self, project_id, grid_model_id):
        return self._manifest(project_id, grid_model_id).get("quality", quality_report())

    def load_arrays(self, project_id, grid_model_id=None):
        project = self._project(project_id)
        manifest = self.grid_store.get_active(project) if grid_model_id is None else self._manifest(project_id, grid_model_id)
        return manifest, self.grid_store.load_arrays(project, manifest)

    def cell_detail(self, project_id, grid_model_id, cell_id_value):
        manifest, arrays = self.load_arrays(project_id, grid_model_id)
        parsed = parse_cell_id(cell_id_value, expected_grid_model_id=grid_model_id, shape=(
            manifest["geometry"]["nlay"],
            manifest["geometry"]["nrow"],
            manifest["geometry"]["ncol"],
        ))
        return self._cell_detail(manifest, arrays, parsed["layer"], parsed["row"], parsed["column"])

    def render_data(self, project_id, grid_model_id, layer=None, include_inactive=False):
        manifest, arrays = self.load_arrays(project_id, grid_model_id)
        nlay, nrow, ncol = manifest["geometry"]["nlay"], manifest["geometry"]["nrow"], manifest["geometry"]["ncol"]
        if nlay * nrow * ncol > MAX_RENDER_CELLS and layer is None:
            raise GridModelValidationError(
                quality_report([grid_item("error", "GRID_RENDER_TOO_LARGE", "render-data", "Request a single layer or smaller range")])
            )
        layers = [int(layer)] if layer is not None else list(range(nlay))
        points = []
        for k in layers:
            if k < 0 or k >= nlay:
                raise ProjectValidationError("layer is outside grid bounds")
            for i in range(nrow):
                for j in range(ncol):
                    if not include_inactive and int(arrays["idomain"][k, i, j]) != 1:
                        continue
                    points.append(self._cell_detail(manifest, arrays, k, i, j, include_footprint=True))
        return {
            "grid_model_id": grid_model_id,
            "status": manifest.get("status"),
            "geometry": manifest["geometry"],
            "generation": manifest["generation"],
            "quality": manifest.get("quality", {}),
            "points": points,
        }

    def rebuild(self, project_id, grid_model_id):
        existing = self._manifest(project_id, grid_model_id)
        return self.create(project_id, existing["generation"])

    def ensure_runnable(self, project_id, grid_model_id):
        manifest, arrays = self.load_arrays(project_id, grid_model_id)
        if manifest.get("status") == "stale":
            raise GridModelValidationError(quality_report([grid_item("error", "GRID_ARTIFACT_STALE", "grid", "Grid is stale; rebuild before running")]))
        quality = manifest.get("quality", {})
        if quality.get("errors"):
            raise GridModelValidationError(quality)
        project = self._project(project_id)
        geology = self.geology_store.get_active(project)
        current_checksum = geology_checksum(geology)
        if current_checksum != manifest.get("provenance", {}).get("geology_checksum"):
            raise GridModelValidationError(
                quality_report([grid_item("error", "GRID_GEOLOGY_CHECKSUM_MISMATCH", "geology_model_id", "Grid geology checksum does not match active geology")])
            )
        return manifest, arrays

    def mark_stale_for_project(self, project_id, reason, geology=None):
        project = self._project(project_id)
        checksum = geology_checksum(geology) if geology else None
        return self.grid_store.mark_active_stale(project, reason, checksum)

    def _validate_geology_for_grid(self, geology_model):
        if not geology_model:
            raise GeologyModelNotFoundError("active geology model not found")
        diagnostics = geology_model.get("diagnostics") or {}
        if not diagnostics.get("valid"):
            raise GeologyModelValidationError(diagnostics)
        derived = geology_model.get("derived_artifacts") or {}
        if derived.get("status") == "stale":
            raise GridModelValidationError(
                quality_report([grid_item("error", "GRID_ARTIFACT_STALE", "geology.derived_artifacts", "Geology derived artifacts are stale; rebuild geology first")])
            )
        if not geology_model.get("boundary"):
            raise GridModelValidationError(
                quality_report([grid_item("error", "BOUNDARY_MISSING", "geology.boundary", "Geology boundary is required")])
            )

    def _generate_arrays(self, geology_model, config):
        boundary_geom = shape(geology_model["boundary"]["geometry"])
        if boundary_geom.is_empty or not boundary_geom.is_valid:
            raise GridModelValidationError(
                quality_report([grid_item("error", "BOUNDARY_INVALID", "boundary", "Invalid boundary cannot generate grid")])
            )
        minx, miny, maxx, maxy = grid_bounds_from_boundary(boundary_geom, config["rotation"])
        width, height = maxx - minx, maxy - miny
        ncol = max(1, int(math.ceil(width / config["cell_size"]["x"])))
        nrow = max(1, int(math.ceil(height / config["cell_size"]["y"])))
        nlay = len((geology_model.get("stratigraphy") or {}).get("formations", []))
        if nlay <= 0:
            raise GridModelValidationError(quality_report([grid_item("error", "GRID_EMPTY_LAYER", "stratigraphy", "At least one formation is required")]))
        if nlay > MAX_NLAY or nrow > MAX_NROW or ncol > MAX_NCOL or nlay * nrow * ncol > MAX_TOTAL_CELLS:
            raise GridModelValidationError(
                quality_report([grid_item("error", "GRID_RESOURCE_LIMIT_EXCEEDED", "generation", "Grid exceeds configured resource limits")])
            )
        delr = np.full(ncol, float(config["cell_size"]["x"]), dtype=float)
        delc = np.full(nrow, float(config["cell_size"]["y"]), dtype=float)
        xorigin, yorigin = float(minx), float(miny)

        x_centers = np.zeros((nrow, ncol), dtype=float)
        y_centers = np.zeros((nrow, ncol), dtype=float)
        cell_polygons = {}
        active_2d = np.zeros((nrow, ncol), dtype=bool)
        overlap_ratio = np.zeros((nrow, ncol), dtype=float)
        for i in range(nrow):
            for j in range(ncol):
                cx, cy = cell_center_xy(xorigin, yorigin, delr, delc, nrow, i, j, config["rotation"])
                x_centers[i, j] = cx
                y_centers[i, j] = cy
                poly = world_cell_polygon(xorigin, yorigin, delr, delc, nrow, i, j, config["rotation"])
                cell_polygons[(i, j)] = poly
                ratio = float(poly.intersection(boundary_geom).area / poly.area) if poly.area > 0 else 0.0
                overlap_ratio[i, j] = ratio
                active_2d[i, j] = ratio >= config["minimum_boundary_overlap"]

        geo_modeler = build_geological_modeler_from_geology_model(geology_model)
        faults = [linestring_points_for_engine(fault) for fault in geology_model.get("faults", [])]
        surfaces = geo_modeler.interpolate_surfaces(x_centers, y_centers, faults)
        formations = (geology_model.get("stratigraphy") or {}).get("formations", [])
        top = None
        botm = np.zeros((nlay, nrow, ncol), dtype=float)
        for k, formation in enumerate(formations):
            layer_id = formation.get("source_layer_id", formation.get("order", k + 1))
            if layer_id not in surfaces:
                raise GridModelValidationError(
                    quality_report([grid_item("error", "GRID_NONFINITE_VALUE", "surfaces", f"Missing surface for formation {formation['formation_id']}")])
                )
            layer_top = np.asarray(surfaces[layer_id]["Top"], dtype=float)
            layer_bot = np.asarray(surfaces[layer_id]["Bottom"], dtype=float)
            if layer_top.shape != (nrow, ncol) or layer_bot.shape != (nrow, ncol):
                raise GridModelValidationError(
                    quality_report([grid_item("error", "GRID_ARRAY_SHAPE_INVALID", "surfaces", "Interpolated surface shape does not match grid")])
                )
            if not np.all(np.isfinite(layer_top)) or not np.all(np.isfinite(layer_bot)):
                raise GridModelValidationError(
                    quality_report([grid_item("error", "GRID_NONFINITE_VALUE", "surfaces", "Interpolated surfaces contain NaN or Infinity")])
                )
            if k == 0:
                top = layer_top
            botm[k] = layer_bot
        arrays = {
            "delr": delr,
            "delc": delc,
            "top": top,
            "botm": botm,
            "idomain": np.zeros((nlay, nrow, ncol), dtype=np.int32),
            "x_centers": x_centers,
            "y_centers": y_centers,
            "overlap_ratio": overlap_ratio,
        }
        layer_tops = np.empty_like(botm)
        layer_tops[0] = top
        if nlay > 1:
            layer_tops[1:] = botm[:-1]
        thickness = layer_tops - botm
        for k in range(nlay):
            arrays["idomain"][k] = (
                active_2d
                & np.isfinite(layer_tops[k])
                & np.isfinite(botm[k])
                & (thickness[k] >= float(config["minimum_thickness"]))
            ).astype(np.int32)
        arrays["thickness"] = thickness
        geometry = {
            "nlay": nlay,
            "nrow": nrow,
            "ncol": ncol,
            "xorigin": xorigin,
            "yorigin": yorigin,
            "rotation": float(config["rotation"]),
            "delr": {"type": "constant", "value": float(config["cell_size"]["x"]), "count": ncol},
            "delc": {"type": "constant", "value": float(config["cell_size"]["y"]), "count": nrow},
            "top": {"shape": [nrow, ncol], "artifact": "top"},
            "botm": {"shape": [nlay, nrow, ncol], "artifact": "botm"},
            "idomain": {"shape": [nlay, nrow, ncol], "artifact": "idomain"},
            "bounds": {"local": [float(minx), float(miny), float(maxx), float(maxy)], "world": list(map(float, boundary_geom.bounds))},
        }
        manifest_stub = {"geometry": geometry, "generation": config}
        quality = build_quality_report(manifest_stub, arrays, boundary_geom=boundary_geom, cell_polygons=cell_polygons)
        return arrays, geometry, quality, cell_polygons

    def _manifest(self, project_id, grid_model_id):
        project = self._project(project_id)
        manifest = self.grid_store.get_active(project)
        if manifest["grid_model_id"] != grid_model_id:
            raise GridModelNotFoundError("grid model not found for project")
        return manifest

    def _cell_detail(self, manifest, arrays, layer, row, column, include_footprint=False):
        geometry = manifest["geometry"]
        nlay, nrow, ncol = geometry["nlay"], geometry["nrow"], geometry["ncol"]
        if not (0 <= layer < nlay and 0 <= row < nrow and 0 <= column < ncol):
            raise ProjectValidationError("cell index is outside grid bounds")
        top = float(arrays["top"][row, column]) if layer == 0 else float(arrays["botm"][layer - 1, row, column])
        bottom = float(arrays["botm"][layer, row, column])
        center_x = float(arrays["x_centers"][row, column])
        center_y = float(arrays["y_centers"][row, column])
        detail = {
            "cell_id": cell_id(manifest["grid_model_id"], layer, row, column),
            "grid_model_id": manifest["grid_model_id"],
            "layer": layer,
            "row": row,
            "column": column,
            "col": column,
            "x": center_x,
            "y": center_y,
            "center": {"x": center_x, "y": center_y, "z": (top + bottom) / 2.0},
            "top": top,
            "bottom": bottom,
            "thickness": top - bottom,
            "idomain": int(arrays["idomain"][layer, row, column]),
            "active": bool(arrays["idomain"][layer, row, column] == 1),
            "head": None,
            "flows": None,
        }
        if include_footprint:
            poly = world_cell_polygon(
                geometry["xorigin"],
                geometry["yorigin"],
                arrays["delr"],
                arrays["delc"],
                nrow,
                row,
                column,
                geometry.get("rotation", 0.0),
            )
            detail["footprint"] = [{"x": float(x), "y": float(y)} for x, y in poly.exterior.coords]
        return detail
