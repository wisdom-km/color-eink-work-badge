"""Manifest for a timestamped candidate export. Not a production authorization."""
import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--dest", required=True)
p.add_argument("--pcb-dir", required=True)
p.add_argument("--models-json", required=True)
p.add_argument("--kind", default="candidate_not_production")
a = p.parse_args()
pcb = Path(a.pcb_dir).resolve()
dest = Path(a.dest).resolve()
# hardware/pcb -> hardware -> repo root
repo = pcb.parent.parent


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args):
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    return (r.stdout or "").strip() if r.returncode == 0 else ""


def normalize_gerber(text):
    return "\n".join(
        s for s in text.splitlines()
        if not s.startswith((
            "%TF.CreationDate,",
            "G04 Created by KiCad ",
            "; #@! TF.CreationDate,",
            "; DRILL file {KiCad ",
        ))
    )


models = json.loads(Path(a.models_json).read_text(encoding="utf-8"))
silk_new = dest / "gerbers" / "badge-B_Silkscreen.gbr"
silk_old = pcb / "output" / "gerbers" / "badge-B_Silkscreen.gbr"
silk = {}
if silk_new.is_file() and silk_old.is_file():
    nnew = normalize_gerber(silk_new.read_text(encoding="utf-8", errors="replace"))
    nold = normalize_gerber(silk_old.read_text(encoding="utf-8", errors="replace"))
    silk = {
        "normalized_equal_to_archived": nnew == nold,
        "fresh_normalized_sha256": hashlib.sha256(nnew.encode()).hexdigest(),
        "archived_normalized_sha256": hashlib.sha256(nold.encode()).hexdigest(),
        "note": "N02: archived output/gerbers B.Silk is expected to differ. "
                "This candidate is still not a production package.",
    }

members = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
kicad = subprocess.run(["kicad-cli", "--version"], capture_output=True, text=True)
data = {
    "kind": a.kind,
    "production_authorized": False,
    "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "git_head": git("rev-parse", "HEAD"),
    "git_status_short": git("status", "--short"),
    "board_sha256": sha256(pcb / "badge.kicad_pcb"),
    "schematic_sha256": sha256(pcb / "badge.kicad_sch"),
    "kicad_cli_version": (kicad.stdout or kicad.stderr or "").strip(),
    "error_level_gate": "ERC/DRC --severity-error --exit-code-violations; not a full-warning pass",
    "full_warnings": "see docs/hardware/drc-warning-register.md; none waived for production",
    "models_missing_count": models.get("missing_count"),
    "models_missing": models.get("missing"),
    "step_cli_zero_is_not_coverage": True,
    "silk_vs_archived": silk,
    "members": members,
    "do_not_use_as_production_package": True,
}
(dest / "manifest.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
print(json.dumps({"kind": data["kind"], "members": len(members), "silk": silk}, indent=2))
