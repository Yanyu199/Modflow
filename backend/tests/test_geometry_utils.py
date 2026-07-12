import zipfile
from pathlib import Path

import fiona
from shapely.geometry import Polygon, mapping

from geometry_utils import parse_shapefile_zip


class FileUploadStub:
    def __init__(self, path):
        self.path = Path(path)

    def save(self, target):
        Path(target).write_bytes(self.path.read_bytes())


def test_parse_shapefile_zip_finds_shp_inside_nested_directory(tmp_path):
    source_dir = tmp_path / "nested" / "boundary"
    source_dir.mkdir(parents=True)
    shp_path = source_dir / "model_boundary.shp"
    polygon = Polygon([(0, 0), (10, 0), (10, 5), (0, 5), (0, 0)])
    schema = {"geometry": "Polygon", "properties": {"id": "int"}}
    with fiona.open(shp_path, "w", driver="ESRI Shapefile", schema=schema) as dst:
        dst.write({"geometry": mapping(polygon), "properties": {"id": 1}})

    zip_path = tmp_path / "boundary.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file_path in source_dir.iterdir():
            zf.write(file_path, arcname=f"nested/boundary/{file_path.name}")

    coords = parse_shapefile_zip(FileUploadStub(zip_path))

    assert coords[0] == {"x": 0.0, "y": 0.0}
    assert coords[-1] == {"x": 0.0, "y": 0.0}
    assert len(coords) == 5
