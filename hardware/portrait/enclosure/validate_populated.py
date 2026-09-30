"""C1 entry; legacy source archived in validation/legacy_before_c1_final."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('c1_validate.py')),run_name="__main__")
