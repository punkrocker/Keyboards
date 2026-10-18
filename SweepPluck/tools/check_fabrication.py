"""Parse the actual upload ZIP with Gerbv and cross-check mask/drill exports."""
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import re
import subprocess
import pcbnew as p

D = Path(__file__).resolve().parents[1]
V = D / "verification"
OUT = V / "fabrication-parser"
OUT.mkdir(exist_ok=True)
ZIP = D / "SweepPluck-JLCPCB.zip"
summary = json.loads((V / "summary.json").read_text())
assert hashlib.sha256(ZIP.read_bytes()).hexdigest() == summary["gerber_zip_sha256"]
with ZipFile(ZIP) as z:
    assert set(z.namelist()) == set(summary["upload_file_hashes"])
    for name in z.namelist():
        assert Path(name).name == name and name.isascii()
        data = z.read(name)
        assert hashlib.sha256(data).hexdigest() == summary["upload_file_hashes"][name]
        (OUT / name).write_bytes(data)

logs = {}
for name in sorted(summary["upload_file_hashes"]):
    result = subprocess.run(["gerbv", "-x", "svg", "-B", "0", "-o",
                             str(OUT / (name + ".svg")), str(OUT / name)],
                            capture_output=True, text=True)
    logs[name] = {"exit_code": result.returncode, "diagnostics": result.stderr.strip()}
    assert result.returncode == 0, (name, result.stderr)
    assert not re.search(r"error|critical|warning", result.stderr, re.I), (name, result.stderr)
    assert (OUT / (name + ".svg")).stat().st_size > 200

def flashes(path):
    text = path.read_text()
    assert "%MOMM*%" in text and "%FSLAX46Y46*%" in text
    assert "%TF." not in text and "%AM" not in text
    positions = []
    current = [0.0, 0.0]
    for line in text.splitlines():
        if not line.startswith(("X", "Y")):
            continue
        for axis, raw in re.findall(r"([XY])(-?\d+)", line):
            current[axis == "Y"] = int(raw) / 1000000
        assert min(current) >= 0
        if "D03" in line:
            positions.append(tuple(current))
    return positions

b = p.LoadBoard(str(D / "SweepPluck.kicad_pcb"))
origin = b.GetDesignSettings().GetAuxOrigin()
ox, oy = p.ToMM(origin.x), p.ToMM(origin.y)
counts = {}
for layer, name in ((p.F_Mask, "TopSolderMask.GTS"), (p.B_Mask, "BottomSolderMask.GBS")):
    actual = flashes(OUT / name)
    expected = [z for f in b.GetFootprints() for z in f.Pads()
                if z.GetLayerSet().Contains(layer)]
    for z in expected:
        px, py = z.GetPosition().x, z.GetPosition().y
        point = (p.ToMM(px) - ox, oy - p.ToMM(py))
        assert any(abs(x - point[0]) < .001 and abs(y - point[1]) < .001 for x, y in actual), (
            "Exported mask opening missing", name, z.GetParent().GetReference(), z.GetNumber(), point)
    counts[name] = {"pcb_openings_checked": len(expected), "gerber_flashes": len(actual)}

outline = (OUT / "BoardOutline.GKO").read_text()
coords = [(int(x) / 1000000, int(y) / 1000000)
          for x, y in re.findall(r"^X(-?\d+)Y(-?\d+)D0[12]\*", outline, re.M)]
assert len(coords) == 8
size = [max(x for x, y in coords) - min(x for x, y in coords),
        max(y for x, y in coords) - min(y for x, y in coords)]
assert size == [95.25, 80.0]
assert min(min(x, y) for x, y in coords) == 0
drills = {}
for name, attr in (("Plated.DRL", p.PAD_ATTRIB_PTH), ("NonPlated.DRL", p.PAD_ATTRIB_NPTH)):
    text = (OUT / name).read_text()
    assert "METRIC" in text and "M48" in text and "M30" in text
    lines = [line for line in text.splitlines() if line.startswith("X")]
    for line in lines:
        assert all(float(x) >= 0 for x in re.findall(r"[XY](-?\d+(?:\.\d+)?)", line))
    expected = sum(z.GetAttribute() == attr for f in b.GetFootprints() for z in f.Pads())
    if attr == p.PAD_ATTRIB_PTH:
        expected += sum(t.Type() == p.PCB_VIA_T for t in b.GetTracks())
    assert len(lines) == expected, (name, len(lines), expected)
    drills[name] = {"operations": len(lines), "slots": sum("G85" in line for line in lines)}

result = {"zip": ZIP.name, "zip_sha256": summary["gerber_zip_sha256"],
          "independent_parser": "Gerbv 2.10.0", "files_parsed": len(logs),
          "parse_errors": 0, "outline_mm": size, "solder_mask_openings": counts,
          "drill_operations": drills, "parser_results": logs,
          "jlcpcb_online_upload_verified": False}
(V / "fabrication-check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
