#!/usr/bin/env bash
# Gated manufacturing export for BADGE-42C.
# Default: error-level ERC/DRC/netlist, then a NEW timestamped candidate directory.
# This is NOT a production-release authorization. Never overwrite output/gerbers
# or output/badge_gerbers.zip. Failures write reports only, never a shop-looking zip.
set -euo pipefail
cd "$(dirname "$0")/.."
PCB_DIR="$(pwd)"
OUT=output
mkdir -p "$OUT"

MODE=candidate
for arg in "$@"; do
  case "$arg" in
    --check-only) MODE=check ;;
    --candidate) MODE=candidate ;;
    --production)
      echo "REFUSED: --production is not authorized. H1 only emits candidates." >&2
      echo "Historical push permission is not a production-package authorization." >&2
      exit 2
      ;;
    -h|--help)
      echo "Usage: $0 [--check-only|--candidate|--production]"
      echo "  --check-only   error ERC/DRC, netlist, BOM classify, 3D inventory"
      echo "  --candidate    same, then gerbers into output/exports/<stamp>/ (default)"
      echo "  --production   refused until Wisdom authorizes a production package"
      exit 0
      ;;
    *)
      echo "unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if ! command -v kicad-cli >/dev/null 2>&1 && ! command -v kicad-cli.exe >/dev/null 2>&1; then
  echo "kicad-cli not on PATH" >&2
  exit 127
fi
KICAD_CLI=kicad-cli
command -v kicad-cli >/dev/null 2>&1 || KICAD_CLI=kicad-cli.exe

if [[ -z "${KICAD9_3DMODEL_DIR:-}" ]]; then
  _cli_path="$(command -v "$KICAD_CLI")"
  _share="$(cd "$(dirname "$_cli_path")/../share/kicad/3dmodels" 2>/dev/null && pwd || true)"
  if [[ -n "$_share" && -d "$_share" ]]; then
    export KICAD9_3DMODEL_DIR="$_share"
  fi
fi

run_or_die() {
  local desc="$1"; shift
  echo "== $desc"
  # Do not use `if ! cmd; then rc=$?` — after a successful `if` test, $? is 0.
  local rc=0
  "$@" || rc=$?
  if [[ "$rc" -ne 0 ]]; then
    echo "FAIL: $desc (rc=$rc) — no manufacturing package written" >&2
    exit "$rc"
  fi
}

echo "== ERC / DRC (error level, --exit-code-violations)"
run_or_die "ERC" "$KICAD_CLI" sch erc --severity-error --exit-code-violations --format report \
  -o "$OUT/erc_errors.rpt" badge.kicad_sch
run_or_die "DRC" "$KICAD_CLI" pcb drc --severity-error --exit-code-violations --format report \
  -o "$OUT/drc_final.rpt" badge.kicad_pcb

resolve_python() {
  local c
  for c in python3 python py; do
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c "import sys; raise SystemExit(0 if sys.version_info[0] >= 3 else 1)" 2>/dev/null; then
        echo "$c"
        return 0
      fi
    fi
  done
  if command -v py >/dev/null 2>&1 && py -3 -c "import sys" 2>/dev/null; then
    echo "py -3"
    return 0
  fi
  echo "Python 3 required (python3, python, or py -3)" >&2
  return 1
}

PY="$(resolve_python)"
# shellcheck disable=SC2086
py() { $PY "$@"; }

run_or_die "ERC report parse" $PY scripts/check_kicad_report.py "$OUT/erc_errors.rpt" --kind erc
run_or_die "DRC report parse" $PY scripts/check_kicad_report.py "$OUT/drc_final.rpt" --kind drc

echo "== netlist + engineering/assembly BOM"
run_or_die "netlist export" "$KICAD_CLI" sch export netlist -o "$OUT/badge.net" badge.kicad_sch
run_or_die "netlist vs design.py" $PY scripts/check_netlist.py
run_or_die "position (back)" "$KICAD_CLI" pcb export pos --side back --format csv --units mm \
  --use-drill-file-origin -o "$OUT/badge_pos_back.csv" badge.kicad_pcb
run_or_die "BOM classify" $PY scripts/classify_bom.py --out-dir "$OUT" --pos "$OUT/badge_pos_back.csv"

echo "== 3D model inventory (missing models do not pass as coverage)"
run_or_die "3D inventory" $PY scripts/check_3d_models.py --pcb-dir "$PCB_DIR" --json-out "$OUT/3d_models.json"
echo "error-level ERC/DRC 0 is not a full-warning pass; see docs/hardware/drc-warning-register.md"

if [[ "$MODE" == "check" ]]; then
  echo "check-only complete; no gerbers, no zip"
  exit 0
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CAND="$OUT/exports/${STAMP}-candidate"
if [[ -e "$CAND" ]]; then
  echo "refusing to reuse existing $CAND" >&2
  exit 1
fi
mkdir -p "$CAND/gerbers"

echo "== candidate gerbers (NOT production; will not touch output/gerbers or badge_gerbers.zip)"
run_or_die "gerbers" "$KICAD_CLI" pcb export gerbers \
  --layers "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
  --subtract-soldermask --no-protel-ext -o "$CAND/gerbers/" badge.kicad_pcb
run_or_die "drill" "$KICAD_CLI" pcb export drill --format excellon --excellon-separate-th \
  --generate-map --map-format gerberx2 -o "$CAND/gerbers/" badge.kicad_pcb
run_or_die "position" "$KICAD_CLI" pcb export pos --side back --format csv --units mm \
  --use-drill-file-origin -o "$CAND/badge_pos_back.csv" badge.kicad_pcb
run_or_die "KiCad grouped BOM" "$KICAD_CLI" sch export bom -o "$CAND/badge_bom_kicad.csv" \
  --fields "Reference,Value,Footprint,Description,LCSC,\${QUANTITY},\${DNP}" \
  --labels "Ref,Value,Footprint,Description,LCSC,Qty,DNP" \
  --group-by "Value,Footprint,LCSC" badge.kicad_sch
run_or_die "BOM classify into candidate" $PY scripts/classify_bom.py --out-dir "$CAND" --pos "$CAND/badge_pos_back.csv"
cp -f "$OUT/3d_models.json" "$CAND/3d_models.json"
cp -f "$OUT/erc_errors.rpt" "$CAND/erc_errors.rpt"
cp -f "$OUT/drc_final.rpt" "$CAND/drc_final.rpt"

if [[ ! -f "$CAND/gerbers/badge-B_Silkscreen.gbr" ]]; then
  echo "candidate missing current badge-B_Silkscreen.gbr" >&2
  exit 1
fi

run_or_die "zip candidate" $PY scripts/zip_dir.py "$CAND/gerbers" "$CAND/badge_gerbers_candidate.zip"
run_or_die "manifest" $PY scripts/write_candidate_manifest.py \
  --dest "$CAND" --pcb-dir "$PCB_DIR" --models-json "$CAND/3d_models.json"

echo "candidate written: $CAND"
echo "NOT a production package. Archived output/gerbers and output/badge_gerbers.zip were not modified."
