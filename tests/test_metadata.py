import json
from pathlib import Path


def test_metadata_json_exists_and_valid():
    repo_root = Path(__file__).resolve().parent.parent
    metadata_path = repo_root / "debim_ingetrazo" / "metadata.json"

    assert metadata_path.is_file(), "metadata.json does not exist"

    with open(metadata_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    required_keys = {
        "id": "debim-ingetrazo",
        "name": "debim — Building-as-Code Loader",
        "version": "0.1.0",
        "author": "PRIDA-TAKON",
        "license": "MIT",
        "description": "Declarative OpenBIM manifest loader and live sync for IngeTrazo",
        "min_ingetrazo_version": "0.5.8",
    }

    for key, expected_val in required_keys.items():
        assert key in data, f"Missing key: {key}"
        assert data[key] == expected_val, f"Mismatch for {key}: expected {expected_val}, got {data[key]}"
