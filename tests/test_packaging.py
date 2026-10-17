import json
import zipfile
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from tools.package_extension import package_extension


def test_package_extension(tmp_path):
    source_dir = repo_root / "debim_ingetrazo"
    output_zip = tmp_path / "debim-ingetrazo.zip"

    sha256_hash = package_extension(source_dir, output_zip)

    assert output_zip.exists()
    assert len(sha256_hash) == 64

    with zipfile.ZipFile(output_zip, "r") as zf:
        namelist = zf.namelist()
        assert "debim_ingetrazo/__init__.py" in namelist
        assert "debim_ingetrazo/metadata.json" in namelist


def test_catalog_entry_updates_sha256():
    catalog_file = repo_root / "catalog_entry.json"
    assert catalog_file.exists()

    with open(catalog_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["id"] == "debim-ingetrazo"
    assert data["version"] == "0.1.0"
    assert "sha256" in data
    assert len(data["sha256"]) == 64
