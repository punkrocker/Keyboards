"""Package the checked v3 project without obsolete footprints or machine state."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import re

D = Path(__file__).resolve().parents[1]
summary = json.loads((D / "verification" / "summary.json").read_text())
assert summary["revision"] == "3.1" and summary["reversible"]
digest = lambda file: hashlib.sha256(file.read_bytes()).hexdigest()
assert digest(D / "SweepPluck.kicad_pcb") == summary["board_sha256"]
assert digest(D / "SweepPluck-gerbers.zip") == summary["gerber_zip_sha256"]
assert digest(D / "SweepPluck-JLCPCB.zip") == summary["gerber_zip_sha256"]
fabrication = json.loads((D / "verification" / "fabrication-check.json").read_text())
assert fabrication["zip_sha256"] == summary["gerber_zip_sha256"]
assert fabrication["files_parsed"] == 9 and fabrication["parse_errors"] == 0
with ZipFile(D / "SweepPluck-gerbers.zip") as z:
    assert set(z.namelist()) == set(summary["upload_file_hashes"])
    for name, expected in summary["upload_file_hashes"].items():
        assert hashlib.sha256(z.read(name)).hexdigest() == expected
    for name, expected in summary["manufacturing_files"].items():
        assert digest(D / "gerbers" / name) == expected

used = set(re.findall(r'\(footprint "SweepPluck:([^"]+)"',
                      (D / "SweepPluck.kicad_pcb").read_text(encoding="utf-8")))
with ZipFile(D / "archive" / "SweepPluck-v2-panel.zip") as z:
    old_modules = {Path(n).name for n in z.namelist() if n.startswith("SweepPluck.pretty/")}
    old_files = set(z.namelist())
known = old_modules | {"ProMicro_Left.kicad_mod", "ProMicro_Right.kicad_mod"}
for file in (D / "SweepPluck.pretty").glob("*.kicad_mod"):
    if file.stem not in used and file.name in known:
        assert file.resolve().is_relative_to(D.resolve())
        file.unlink()
for name in ("compact-build.log", "compact-import.log"):
    file = D / "verification" / name
    if file.is_file() and "verification/" + name in old_files:
        assert file.resolve().is_relative_to(D.resolve())
        file.unlink()

package = D / "SweepPluck-v3-reversible.zip"
files = [file for file in D.iterdir() if file.is_file() and
         file != package and file.suffix != ".kicad_prl"]
files += [D / "SweepPluck.pretty" / (name + ".kicad_mod") for name in sorted(used)]
files += list((D / "tools").glob("*.py"))
files += [D / "gerbers" / name for name in summary["manufacturing_files"]]
files += [D / "archive" / "SweepPluck-v2-panel.zip", D / "archive" / "SweepPluck-v1-split.zip"]
for name in ("summary.json", "check-inputs.json", "placement-checks.json", "fabrication-check.json", "routing.log",
             "drc-SweepPluck.json", "drc-SweepPluck-plate.json", "erc-SweepPluck.json",
             "SweepPluck.xml", "SweepPluck.dsn", "SweepPluck.ses"):
    files.append(D / "verification" / name)
assert all(file.is_file() for file in files)
with ZipFile(package, "w", ZIP_DEFLATED) as z:
    for file in sorted(files):
        z.write(file, file.relative_to(D).as_posix())
with ZipFile(package) as z:
    assert z.testzip() is None
print(f"Packaged {len(files)} files, {len(used)} active footprints: {package.name} ({package.stat().st_size} bytes)")
