#!/usr/bin/env python3
"""Package only the integration and public instructions; never vehicle captures."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
component = ROOT / "custom_components" / "obd_connect"
version = json.loads((component / "manifest.json").read_text())["version"]
output = ROOT / "artifacts" / f"obd-connect-{version}.zip"
output.parent.mkdir(exist_ok=True)
def add(archive, path, name):
    info = ZipInfo(str(name), date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, path.read_bytes())

with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for path in sorted(component.rglob("*")):
        if path.is_file() and path.suffix in (".py", ".json", ".png", ".svg") and "__pycache__" not in path.parts:
            add(archive, path, path.relative_to(ROOT))
    add(archive, ROOT / "hacs.json", "hacs.json")
    add(archive, ROOT / "docs" / "OBD_CONNECT_SETUP.md", "README.md")
checksum = hashlib.sha256(output.read_bytes()).hexdigest()
output.with_suffix(".zip.sha256").write_text(f"{checksum}  {output.name}\n")
print(output.relative_to(ROOT))
print(checksum)
