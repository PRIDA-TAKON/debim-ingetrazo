#!/usr/bin/env python3
"""
Packaging script for debim-ingetrazo extension.
Packages debim_ingetrazo directory into dist/debim-ingetrazo.zip
and outputs the SHA-256 digest.
"""

import hashlib
import os
import zipfile
from pathlib import Path


def package_extension(source_dir: Path, output_zip: Path) -> str:
    """
    Compresses source_dir into output_zip and returns the SHA-256 hash of the zip file.
    """
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    if output_zip.exists():
        output_zip.unlink()

    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.endswith('.pyc') or file.startswith('.'):
                    continue
                file_path = Path(root) / file
                arcname = file_path.relative_to(source_dir.parent)
                zipf.write(file_path, arcname)

    sha256 = hashlib.sha256()
    with open(output_zip, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)

    return sha256.hexdigest()


def main():
    repo_root = Path(__file__).resolve().parent.parent
    source_dir = repo_root / "debim_ingetrazo"
    output_zip = repo_root / "dist" / "debim-ingetrazo.zip"

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory {source_dir} does not exist.")

    digest = package_extension(source_dir, output_zip)
    print(f"Extension packaged successfully: {output_zip}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
