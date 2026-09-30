"""CAD environment smoke test. Test fixture is NOT an enclosure proposal."""
from pathlib import Path
import json
import platform
import tempfile
import cadquery as cq
from cad_helpers import box, rounded_box, cylinder, export_part, inspect, overlap_volume, render_shapes

HERE = Path(__file__).resolve().parent
OUT = HERE / "validation"
OUT.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="badge-cad-smoke-") as path:
    base = Path(path) / "fixture"
    outer = rounded_box(0, 0, 0, 24, 34, 6, 2)
    opening = box(3, 3, -1, 21, 31, 7)
    fixture = outer.cut(opening).cut(cylinder(1.5, 17, -1, 7, 1))
    export_part(fixture, base)
    step = cq.importers.importStep(str(base.with_suffix(".step"))).val()
    report = {
        "type": "tool_smoke_test_not_product_validation",
        "python": platform.python_version(),
        "cadquery": cq.__version__,
        "fixture": inspect(fixture),
        "step_roundtrip": inspect(step),
        "step_volume_delta_mm3": abs(step.Volume() - fixture.Volume()),
        "step_bytes": base.with_suffix(".step").stat().st_size,
        "stl_bytes": base.with_suffix(".stl").stat().st_size,
        "known_non_overlap_mm3": overlap_volume(fixture, opening),
        "status": "PASS",
    }
    assert fixture.isValid() and step.isValid()
    assert len(fixture.Solids()) == len(step.Solids()) == 1
    assert report["step_volume_delta_mm3"] < 1e-6
    assert report["known_non_overlap_mm3"] < 1e-6
    render_shapes([(fixture, "#2b3548")], OUT / "cad_tool_smoke.png", "CAD tool smoke test | NOT a product model")
    (OUT / "cad_tool_smoke.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
