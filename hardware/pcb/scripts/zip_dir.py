"""Zip a directory to a new archive. Fails if zip.exe is missing from PATH."""
import sys
import zipfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
dest = Path(sys.argv[2]).resolve()
if dest.exists():
    raise SystemExit("refusing to overwrite existing zip: %s" % dest)
dest.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
    files = sorted(p for p in root.rglob("*") if p.is_file())
    if not files:
        raise SystemExit("no files to zip in %s" % root)
    for p in files:
        z.write(p, p.relative_to(root).as_posix())
print("wrote", dest, "files", len(files))
