"""Small, editable CadQuery/OCC primitives. Units: mm; XY front view, Y up.

Mechanical implementation only. Product dimensions must come from design.py;
this module deliberately contains no badge geometry or hardware defaults.
"""
from pathlib import Path
import cadquery as cq


def box(x0, y0, z0, x1, y1, z1):
    if min(x1 - x0, y1 - y0, z1 - z0) <= 0:
        raise ValueError("Box must have positive dimensions")
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def rounded_box(x0, y0, z0, x1, y1, z1, radius):
    raw = cq.Workplane("XY").newObject([box(x0, y0, z0, x1, y1, z1)])
    return raw.edges("|Z").fillet(radius).val()


def cylinder(x, y, z0, z1, diameter):
    return cq.Solid.makeCylinder(diameter / 2, z1 - z0, cq.Vector(x, y, z0))


def front_box(rect, z0, z1):
    """Front-view X right, Y down rectangle -> native X right, Y up solid."""
    x0, y0, x1, y1 = rect
    return box(x0, -y1, z0, x1, -y0, z1)


def export_part(shape, target_base):
    target_base = Path(target_base)
    target_base.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(shape, str(target_base.with_suffix(".step")))
    cq.exporters.export(shape, str(target_base.with_suffix(".stl")), tolerance=0.035, angularTolerance=0.12)


def overlap_volume(a, b):
    return a.intersect(b).Volume()


def inspect(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    bound = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, bound, False, False)
    x0, y0, z0, x1, y1, z1 = bound.Get()
    return {
        "valid": bool(shape.isValid()),
        "solids": len(shape.Solids()),
        "volume_mm3": shape.Volume(),
        "bbox_mm": [x1-x0, y1-y0, z1-z0],
        "bbox_min_mm": [x0, y0, z0],
        "bbox_max_mm": [x1, y1, z1],
    }


from render_mesh import render_shapes
