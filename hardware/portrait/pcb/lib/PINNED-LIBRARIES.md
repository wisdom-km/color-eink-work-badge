# Pinned KiCad libraries

Only footprint files actually used by P36 were copied from this cloud computer's official KiCad9 libraries. The required symbol libraries are copied whole to preserve inheritance and exact comparison. Generated KiCad10 ERC/DRC resolves to these project-local snapshots rather than an unrelated globally installed version. This prevents version-induced library mismatch warnings; it does not suppress geometric or electrical rule checks.

Official KiCad library licensing remains unchanged: CC-BY-SA4.0 with the KiCad Libraries Exception where applicable. See https://www.kicad.org/libraries/license/ . Project Espressif and HRO footprints retain the existing repository attributions. Custom FH34 geometry is derived from Hirose EDC-159714-50-08 recommended land pattern; verify orientation with panel sample before fabrication.
