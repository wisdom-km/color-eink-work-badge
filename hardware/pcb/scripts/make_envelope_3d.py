"""Build envelope STEP files for missing J3/J2 models. Not vendor CAD."""
import os
import sys

freecad_bin = r"D:\FreeCAD\bin"
if os.path.isdir(freecad_bin) and freecad_bin not in sys.path:
    sys.path.insert(0, freecad_bin)
    sys.path.insert(0, os.path.join(freecad_bin, "Lib"))

import FreeCAD  # noqa: E402
import Part  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "lib", "3d"))
os.makedirs(OUT, exist_ok=True)


def box(name, xyz, dest):
    # xyz is (x, y, z) size in mm, origin at body center, bottom on z=0
    x, y, z = xyz
    solid = Part.makeBox(x, y, z, FreeCAD.Vector(-x / 2, -y / 2, 0))
    doc = FreeCAD.newDocument(name)
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = solid
    Part.export([obj], dest)
    FreeCAD.closeDocument(doc.Name)
    print("wrote", dest, "mm", xyz)


def main():
    # HRO TYPE-C-31-M-14 typical body; offset in the footprint is (0,-2.7,0).
    box("TYPE-C-31-M-14", (8.94, 7.30, 3.25),
        os.path.join(OUT, "TYPE-C-31-M-14.step"))
    # JST SM02B-SHLS-TF outline (SHL 1.0 mm 2P). Envelope, not official JST CAD.
    box("JST_SHL_SM02B-SHLS-TF", (6.6, 4.25, 1.90),
        os.path.join(OUT, "JST_SHL_SM02B-SHLS-TF_1x02-1MP_P1.00mm_Horizontal.step"))


if __name__ == "__main__":
    main()
