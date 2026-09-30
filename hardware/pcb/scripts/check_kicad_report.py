"""Fail if an error-level KiCad ERC/DRC report text still lists violations.

Used after kicad-cli returned 0, as a second check for versions that write
'Found N' without --exit-code-violations. Does not interpret warnings.
"""
import argparse
import re
import sys

p = argparse.ArgumentParser()
p.add_argument("report")
p.add_argument("--kind", choices=("erc", "drc"), required=True)
a = p.parse_args()
text = open(a.report, encoding="utf-8", errors="replace").read()
problems = []
if re.search(r"Found\s+[1-9]\d*\s+(?:DRC\s+|ERC\s+)?violations", text, re.I):
    problems.append("Found N violations with N>0")
if a.kind == "drc" and re.search(r"Found\s+[1-9]\d*\s+unconnected", text, re.I):
    problems.append("Found N unconnected with N>0")
m = re.search(r"(\d+)\s*个错误", text)
if m and int(m.group(1)) > 0:
    problems.append("%s errors in Chinese summary" % m.group(1))
# Fake kicad-cli in fault_probes writes a bare "Found 1 violation" line.
if re.search(r"Found\s+[1-9]\d*\s+violation\b", text, re.I):
    problems.append("Found N violation with N>0")
if problems:
    print("%s report is not clean: %s" % (a.kind.upper(), "; ".join(problems)), file=sys.stderr)
    sys.exit(1)
print("%s report has no error-level hits" % a.kind.upper())
