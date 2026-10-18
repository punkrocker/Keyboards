"""Generate and verify the reversible, single-half SweepPluck v3 PCB.

Run with KiCad's Python (pcbnew), not a generic Python environment.
The v2 source is read from archive/SweepPluck-v2-panel.zip.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import argparse
import csv
import hashlib
import html
import json
import math
import re
import subprocess
import uuid
import xml.etree.ElementTree as ET

import pcbnew as p


D = Path(__file__).resolve().parents[1]
V = D / "verification"
NAME = "SweepPluck"
REVISION = "3.1"
BOARD = D / (NAME + ".kicad_pcb")
L, R, TOP, BOTTOM = 35.475, 130.725, 50.475, 130.475
MCU_X, MCU_F_Y, MCU_B_Y = 54.5, 117.25, 119.79
MCU_PINS = {
    "1": "TX", "2": "RX", "3": "GND", "4": "GND", "5": "SDA",
    "6": "SCL", "7": "D4", "8": "C6", "9": "D7", "10": "E6",
    "11": "B4", "12": "B5", "13": "B6", "14": "B2", "15": "B3",
    "16": "B1", "17": "F7", "18": "F6", "19": "F5", "20": "F4",
    "21": "VCC", "22": "RST", "23": "GND", "24": "RAW",
}
# These terminal locations are the original Sweep High universal footprint's
# holes. Switch contacts are nonpolar: the upper families exchange contacts
# when flipped, whereas Choc's centre terminal keeps its ground assignment.
SWITCH_TERMINALS = {
    "MX": ((-3.8, -2.55), (2.54, -5.08)),
    "Alps": ((-2.5, -4), (5, -5.55)),
    "Choc_V1_V2": ((-5.1, 3.9), (0, 5.9)),
}


def xy(x, y):
    return p.VECTOR2I(p.FromMM(x), p.FromMM(y))


def mm(point):
    return (p.ToMM(point.x), p.ToMM(point.y))


def q(value):
    return json.dumps(str(value), ensure_ascii=False)


def uid():
    return str(uuid.uuid4())


def base_net(name):
    return name[:-2] if name.endswith("_L") else name


def archived_board():
    V.mkdir(exist_ok=True)
    path = V / "v2-reference.kicad_pcb"
    with ZipFile(D / "archive" / "SweepPluck-v2-panel.zip") as z:
        path.write_bytes(z.read("SweepPluck.kicad_pcb"))
    return p.LoadBoard(str(path))


def pin_map(footprint):
    result = {}
    for pad in footprint.Pads():
        if pad.GetNumber():
            name = base_net(pad.GetNetname())
            if pad.GetNumber() in result:
                assert result[pad.GetNumber()] == name
            result[pad.GetNumber()] = name
    return result


def net(board, name):
    if not name:
        return None
    found = board.FindNet(name)
    if found and found.GetNetCode():
        return found
    found = p.NETINFO_ITEM(board, name)
    board.Add(found)
    return found


def assign(board, footprint, mapping):
    for pad in footprint.Pads():
        found = net(board, mapping.get(pad.GetNumber(), ""))
        if found:
            pad.SetNet(found)
        else:
            pad.SetNetCode(0)


def footprint(board, reference, value, library, position, board_only=False):
    f = p.FOOTPRINT(board)
    f.SetReference(reference)
    f.SetValue(value)
    f.SetFPID(p.LIB_ID(NAME, library))
    f.SetPosition(xy(*position))
    f.SetAttributes(p.FP_BOARD_ONLY if board_only else p.FP_THROUGH_HOLE)
    f.Reference().SetVisible(False)
    f.Value().SetVisible(False)
    board.Add(f)
    return f


def pad(f, number, position, size, drill=None, layer=None, npth=False):
    z = p.PAD(f)
    z.SetNumber(number)
    z.SetPosition(f.GetPosition() + xy(*position))
    z.SetSize(xy(*size))
    if drill is None:
        z.SetAttribute(p.PAD_ATTRIB_SMD)
        z.SetShape(p.PAD_SHAPE_RECT)
        layers = p.LSET()
        for item in (layer, p.F_Mask if layer == p.F_Cu else p.B_Mask,
                     p.F_Paste if layer == p.F_Cu else p.B_Paste):
            layers.AddLayer(item)
    else:
        z.SetAttribute(p.PAD_ATTRIB_NPTH if npth else p.PAD_ATTRIB_PTH)
        z.SetShape(p.PAD_SHAPE_CIRCLE if size[0] == size[1] else p.PAD_SHAPE_OVAL)
        z.SetDrillSize(xy(*drill))
        z.SetDrillShape(p.PAD_DRILL_SHAPE_CIRCLE if drill[0] == drill[1]
                        else p.PAD_DRILL_SHAPE_OBLONG)
        layers = p.LSET(p.PAD.UnplatedHoleMask() if npth else p.PAD.PTHMask())
    z.SetLayerSet(layers)
    f.Add(z)
    return z


def fp_line(f, a, b, layer, width=.12):
    s = p.PCB_SHAPE(f)
    s.SetShape(p.SHAPE_T_SEGMENT)
    s.SetStart(f.GetPosition() + xy(*a))
    s.SetEnd(f.GetPosition() + xy(*b))
    s.SetLayer(layer)
    s.SetWidth(p.FromMM(width))
    f.Add(s)


def fp_rect(f, bounds, layers=(p.F_Fab, p.B_Fab)):
    x1, y1, x2, y2 = bounds
    points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    for layer in layers:
        for i, a in enumerate(points):
            fp_line(f, a, points[(i + 1) % 4], layer)


def label(board, string, x, y, layer=p.F_SilkS, size=.8):
    t = p.PCB_TEXT(board)
    t.SetText(string)
    t.SetPosition(xy(x, y))
    t.SetTextSize(xy(size, size))
    t.SetTextThickness(p.FromMM(.12))
    t.SetLayer(layer)
    t.SetMirrored(layer == p.B_SilkS)
    board.Add(t)


def rectangle(board, x1, y1, x2, y2):
    polygon(board, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)])


def polygon(board, points):
    for i, a in enumerate(points):
        s = p.PCB_SHAPE()
        s.SetShape(p.SHAPE_T_SEGMENT)
        s.SetStart(xy(*a))
        s.SetEnd(xy(*points[(i + 1) % len(points)]))
        s.SetLayer(p.Edge_Cuts)
        s.SetWidth(p.FromMM(.05))
        board.Add(s)


def switch(board, number, position):
    f = footprint(board, "SW" + str(number), "SW_Push", "Universal_Reversible", position)
    for side in (-1, 1):
        pad(f, "", (side * 5.315, 0), (2.17, 1.8), (2.17, 1.8), npth=True)
    pad(f, "", (0, 0), (4.9, 4.9), (4.9, 4.9), npth=True)
    for side, terminal in ((-1, "1"), (1, "2")):
        pad(f, terminal, (side * 3.8, -2.55), (2.2, 2.2), (1.4, 1.4))
        # One continuous plated slot includes the original Alps circle and the
        # original MX slot. Separate overlapping drills are not manufactured.
        pad(f, terminal, (side * 2.5, -4.5375), (2.4, 3.475), (1.4, 2.475))
        pad(f, terminal, (side * 5, -5.55), (2.2, 1.5), (1, .5))
        pad(f, "1", (side * 5.1, 3.9), (2.2, 1.6), (1, .5))
    pad(f, "2", (0, 5.9), (2.2, 1.5), (1, .5))
    fp_rect(f, (-9.525, -9.525, 9.525, 9.525), (p.Dwgs_User,))
    for layer in (p.F_Fab, p.B_Fab):
        fp_rect(f, (-7, -7, 7, 7), (layer,))
    assign(board, f, {"1": "Switch" + str(number), "2": "GND"})
    return f


def controller(board, source):
    # One logical component, two alternative physical socket sets. Numbering
    # both sets identically preserves the exact MCU GPIO/power pin map.
    f = footprint(board, "U1", "ProMicro_DualRow", "ProMicro_DualRow", (MCU_X, MCU_F_Y))
    ox, oy = mm(source.GetPosition())
    for old in source.Pads():
        px, py = mm(old.GetPosition())
        dx, dy = px - ox, py - oy
        for back in (False, True):
            yy = MCU_B_Y - MCU_F_Y - dy if back else dy
            pad(f, old.GetNumber(), (dx, yy), mm(old.GetSize()), (1, 1))
    for back, fab, silk in ((False, p.F_Fab, p.F_SilkS), (True, p.B_Fab, p.B_SilkS)):
        dy = MCU_B_Y - MCU_F_Y if back else 0
        fp_rect(f, (-18.3, dy - 8.9, 14.75, dy + 8.9), (fab, silk))
        fp_rect(f, (-21.2, dy - 3.75, -18.3, dy + 3.75), (fab,))
    assign(board, f, pin_map(source))
    return f


def power_switch(board, mapping):
    f = footprint(board, "SW_POWER1", "SW_SPDT", "Power_Reversible", (78.5, 112))
    f.SetAttributes(p.FP_SMD)
    for x in (-1.5, 1.5):
        pad(f, "", (x, 0), (.9, .9), (.9, .9), npth=True)
    for layer, mirror in ((p.F_Cu, 1), (p.B_Cu, -1)):
        for x in (-3.7, 3.7):
            for y in (-1.1, 1.1):
                pad(f, "", (x, y), (.9, .9), layer=layer)
        for num, x in (("1", -2.25), ("2", .75), ("3", 2.25)):
            pad(f, num, (mirror * x, -2.075), (.9, 1.25), layer=layer)
    fp_rect(f, (-3.3, -1.35, 3.3, 1.5))
    fp_rect(f, (-1.95, -3.85, 1.95, -1.35))
    assign(board, f, mapping)
    return f


def reset_switch(board):
    f = footprint(board, "RSW1", "SW_Push_Reset", "Reset_Reversible", (78.5, 123))
    f.SetAttributes(p.FP_SMD)
    for layer in (p.F_Cu, p.B_Cu):
        pad(f, "1", (-1.7, 0), (.9, 1.7), layer=layer)
        pad(f, "2", (1.7, 0), (.9, 1.7), layer=layer)
    fp_rect(f, (-1.7, -1.4, 1.7, 1.4))
    assign(board, f, {"1": "GND", "2": "RESET"})
    return f


def jack(board, source):
    f = p.Cast_to_FOOTPRINT(source.Duplicate(False))
    f.SetParent(board)
    f.SetReference("J1")
    f.SetFPID(p.LIB_ID(NAME, "TRRS_Reversible"))
    if f.GetLayer() != p.F_Cu:
        f.Flip(f.GetPosition(), p.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(180)
    f.SetPosition(xy(89, 129))
    f.Reference().SetVisible(False)
    f.Value().SetVisible(False)
    board.Add(f)
    assign(board, f, pin_map(source))
    return f


def save_project():
    rules = {
        "min_clearance": .2, "min_copper_edge_clearance": .25,
        "min_track_width": .2, "min_via_diameter": .6,
        "min_through_hole_diameter": .3, "min_hole_to_hole": .25,
    }
    project = {
        "meta": {"filename": NAME + ".kicad_pro", "version": 1},
        "board": {"design_settings": {"rules": rules}},
        "net_settings": {
            "classes": [{"name": "Default", "clearance": .2, "track_width": .25,
                         "via_diameter": .6, "via_drill": .3}], "version": 3},
    }
    (D / (NAME + ".kicad_pro")).write_text(json.dumps(project, indent=2), encoding="utf-8")


def limits(board):
    settings = board.GetDesignSettings()
    settings.m_MinClearance = p.FromMM(.2)
    settings.m_CopperEdgeClearance = p.FromMM(.25)
    settings.m_TrackMinWidth = p.FromMM(.2)
    settings.m_HoleClearance = p.FromMM(.25)


def build():
    old = archived_board()
    refs = {f.GetReference(): f for f in old.GetFootprints()}
    b = p.BOARD()
    b.SetFileName(str(BOARD))
    b.SetCopperLayerCount(2)
    b.GetDesignSettings().SetBoardThickness(p.FromMM(1.6))
    for f in old.GetFootprints():
        if p.ToMM(f.GetPosition().x) < 133 and "keyswitch_" in str(f.GetFPID().GetLibItemName()):
            number = next(int(re.fullmatch(r"Switch(\d+)", z.GetNetname()).group(1))
                          for z in f.Pads() if re.fullmatch(r"Switch(\d+)", z.GetNetname()))
            switch(b, number, mm(f.GetPosition()))
    controller(b, refs["U1"])
    power_switch(b, pin_map(refs["SW_POWER1"]))
    reset_switch(b)
    jack(b, refs["J1"])
    for reference, position, name in (("BATP1", (72, 111), "BAT"),
                                       ("BATG1", (72, 125), "GND")):
        f = footprint(b, reference, "Battery_" + name, "Battery_Pad", position)
        pad(f, "1", (0, 0), (2.1, 2.1), (.9, .9))
        assign(b, f, {"1": name})
    for reference in ("H1", "H2"):
        f = footprint(b, reference, "MountingHole_3.2mm", "MountingHole_3.2mm",
                      mm(refs[reference].GetPosition()), board_only=True)
        pad(f, "", (0, 0), (3.2, 3.2), (3.2, 3.2), npth=True)
    rectangle(b, L, TOP, R, BOTTOM)
    label(b, f"SweepPluck v{REVISION} LEFT", 108, 129, size=.8)
    label(b, f"SweepPluck v{REVISION} RIGHT", 108, 129, p.B_SilkS, .8)
    # Label each socket row outside its copper, with no crowded pin labels.
    label(b, "L", 70.5, 109.64, size=.8)
    label(b, "L", 70.5, 124.86, size=.8)
    label(b, "R", 70.5, 112.18, p.B_SilkS, .8)
    label(b, "R", 70.5, 127.40, p.B_SilkS, .8)
    label(b, "FACE DOWN", MCU_X, MCU_F_Y, size=.8)
    label(b, "FACE DOWN", MCU_X, MCU_B_Y, p.B_SilkS, .8)
    label(b, "TX", 37.8, MCU_F_Y - 7.6114, size=.8)
    label(b, "RAW", 37.8, MCU_F_Y + 7.6086, size=.8)
    label(b, "RAW", 37.8, MCU_B_Y - 7.6086, p.B_SilkS, .8)
    label(b, "TX", 37.8, MCU_B_Y + 7.6114, p.B_SilkS, .8)
    for layer in (p.F_SilkS, p.B_SilkS):
        label(b, "+", 72, 108.9, layer, .8)
        label(b, "-", 72, 127.2, layer, .8)
        label(b, "PWR", 78.5, 115, layer, .8)
        label(b, "RST", 78.5, 126, layer, .8)
    limits(b)
    finish(b)
    assert p.ExportSpecctraDSN(b, str(V / (NAME + ".dsn")))
    dsn = V / (NAME + ".dsn")
    content = dsn.read_text()
    content = re.sub(r"\(clearance (?:200|50)\b", "(clearance 300", content)
    content = content.replace("(width 200)", "(width 250)")
    dsn.write_text(content)
    print("Generated one reversible 17-key PCB, 95.25 x 80 mm")


def schematic(board):
    root = uid()
    symbols, instances, annotations = [], [], []
    components = [f for f in board.GetFootprints() if not f.GetAttributes() & p.FP_BOARD_ONLY]
    components.sort(key=lambda f: (not f.GetReference().startswith("SW"), f.GetReference()))
    key_index = aux_index = 0
    effects = "(effects (font (size 1 1)))"
    small = "(effects (font (size .8 .8)))"
    for i, f in enumerate(components):
        ref, value = f.GetReference(), f.GetValue()
        mapping = pin_map(f)
        # A switch's physical mirrored contact numbers may interchange, but
        # these two logical terminals always connect GPIO to ground.
        is_key = bool(re.fullmatch(r"SW\d+", ref))
        if is_key:
            x, y = 30.48 + (key_index % 5) * 45.72, 30.48 + (key_index // 5) * 30.48
            key_index += 1
        elif ref == "U1":
            x, y = 309.88, 25.4
        else:
            x, y = 30.48 + (aux_index % 5) * 60.96, 185.42 + (aux_index // 5) * 45.72
            aux_index += 1
        lib_id = NAME + ":P" + str(i)
        fp = NAME + ":" + str(f.GetFPID().GetLibItemName())
        height = (len(mapping) + 1) * 2.54
        props = (f'(property "Reference" {q(ref)} (at 0 3 0) {effects}) '
                 f'(property "Value" {q(value)} (at 0 0 0) {effects}) '
                 f'(property "Footprint" {q(fp)} (at 0 0 0) {effects} (hide yes))')
        pins = []
        for k, num in enumerate(mapping):
            label_name = MCU_PINS[num] if ref == "U1" else num
            pins.append(f'(pin passive line (at -11.43 {-2.54 * (k + 1):.4f} 0) '
                        f'(length 5.08) (name {q(label_name)} {small}) (number {q(num)} {small}))')
        symbols.append(f'(symbol {q(lib_id)} (pin_names (offset 0)) (in_bom yes) '
                       f'(on_board yes) {props} (symbol "P{i}_0_1" '
                       f'(rectangle (start -6.35 0) (end 6.35 {-height:.4f}) '
                       f'(stroke (width .254) (type default)) (fill (type background)))) '
                       f'(symbol "P{i}_1_1" {" ".join(pins)}))')
        ident = uid()
        f.SetPath(p.KIID_PATH("/" + root + "/" + ident))
        iprops = (f'(property "Reference" {q(ref)} (at {x} {y - 3} 0) {effects}) '
                  f'(property "Value" {q(value)} (at {x} {y} 0) {effects}) '
                  f'(property "Footprint" {q(fp)} (at {x} {y} 0) {effects} (hide yes))')
        instance_pins = " ".join(f'(pin {q(num)} (uuid {uid()}))' for num in mapping)
        instances.append(f'(symbol (lib_id {q(lib_id)}) (at {x} {y} 0) (unit 1) '
                         f'(in_bom yes) (on_board yes) (dnp no) (uuid {ident}) {iprops} '
                         f'{instance_pins} (instances (project "{NAME}" '
                         f'(path "/{root}" (reference {q(ref)}) (unit 1)))))')
        for k, name in enumerate(mapping.values()):
            px, py = x - 11.43, y + (k + 1) * 2.54
            if name and not name.startswith("unconnected-"):
                annotations.append(f'(global_label {q(name)} (shape passive) '
                                   f'(at {px:.4f} {py:.4f} 0) {small} (uuid {uid()}))')
            else:
                annotations.append(f'(no_connect (at {px:.4f} {py:.4f}) (uuid {uid()}))')
    notes = [
        (25.4, 12.7, "17 direct GPIO keys - same PCB for both hands"),
        (270, 100, "U1: One controller, two alternative socket sets.\nLEFT: use L rows from F side.\nRIGHT: use R rows from B side.\nModule components FACE DOWN towards keyboard PCB.\nFit ONE controller per PCB. No MCU jumpers."),
        (25.4, 243.84, "Left: keys and accessories on F side; controller in L rows.\nRight: flip PCB, keys and accessories on B side; controller in R rows.\nTRRS: R1=SERIAL (RX), R2=VCC, T/S=GND.\nSW_POWER1 has F/B pads; fit one switch on the key side."),
    ]
    for x, y, note in notes:
        annotations.append(f'(text {q(note)} (at {x} {y} 0) '
                           '(effects (font (size 1.2 1.2)) (justify left)) '
                           f'(uuid {uid()}))')
    content = (f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {root}) '
               '(paper "A3") (title_block (title "SweepPluck reversible 17-key half") '
               f'(rev "{REVISION}")) (lib_symbols ' + "\n".join(symbols) + ")\n" +
               "\n".join(annotations + instances) +
               ' (sheet_instances (path "/" (page "1"))))\n')
    (D / (NAME + ".kicad_sch")).write_text(content, encoding="utf-8")
    library = "\n".join(s.replace('(symbol "' + NAME + ':', '(symbol "', 1) for s in symbols)
    (D / (NAME + ".kicad_sym")).write_text(
        '(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n' +
        library + "\n)", encoding="utf-8")
    (D / "sym-lib-table").write_text(
        f'(sym_lib_table (version 7) (lib (name "{NAME}") (type "KiCad") '
        f'(uri "${{KIPRJMOD}}/{NAME}.kicad_sym") (options "") '
        '(descr "Reversible direct GPIO pin wiring")))\n', encoding="utf-8")


def plate(board):
    out = p.BOARD()
    # The lower outer area is open to both alternative MCU module positions.
    polygon(out, [(L, TOP), (R, TOP), (R, BOTTOM), (93, BOTTOM), (93, 108), (L, 108)])
    for f in board.GetFootprints():
        x, y = mm(f.GetPosition())
        if re.fullmatch(r"SW\d+", f.GetReference()):
            rectangle(out, x - 7, y - 7, x + 7, y + 7)
        elif f.GetReference().startswith("H"):
            c = p.PCB_SHAPE()
            c.SetShape(p.SHAPE_T_CIRCLE)
            c.SetCenter(xy(x, y))
            c.SetEnd(xy(x + 1.6, y))
            c.SetLayer(p.Edge_Cuts)
            c.SetWidth(p.FromMM(.05))
            out.Add(c)
    p.SaveBoard(str(D / (NAME + "-plate.kicad_pcb")), out)


def finish(board):
    limits(board)
    board.GetDesignSettings().SetAuxOrigin(xy(L, BOTTOM))
    # Specctra routing imports may replace pad layer sets with copper-only
    # sets. Restore all solderable through-hole openings before saving.
    for f in board.GetFootprints():
        for z in f.Pads():
            if z.GetAttribute() == p.PAD_ATTRIB_PTH:
                z.SetLayerSet(p.LSET(p.PAD.PTHMask()))
            elif z.GetAttribute() == p.PAD_ATTRIB_NPTH:
                z.SetLayerSet(p.LSET(p.PAD.UnplatedHoleMask()))
    for item in board.GetDrawings():
        if hasattr(item, "GetText") and item.GetText().startswith("SweepPluck v3"):
            item.SetText(re.sub(r"SweepPluck v3(?:\.\d+)?", f"SweepPluck v{REVISION}", item.GetText()))
    board.GetTitleBlock().SetTitle("SweepPluck reversible 17-key half")
    board.GetTitleBlock().SetRevision(REVISION)
    save_project()
    schematic(board)
    plate(board)
    p.SaveBoard(str(BOARD), board)
    library = D / (NAME + ".pretty")
    library.mkdir(exist_ok=True)
    plugin = p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP)
    for f in board.GetFootprints():
        plugin.FootprintSave(str(library), f)
    (D / "fp-lib-table").write_text(
        f'(fp_lib_table (version 7) (lib (name "{NAME}") (type "KiCad") '
        f'(uri "${{KIPRJMOD}}/{NAME}.pretty") (options "") '
        '(descr "Local reversible footprints")))\n', encoding="utf-8")
    with (D / (NAME + "-pins.csv")).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["reference", "pad", "net", "x_mm", "y_mm", "copper_layers",
                         "assembly", "drill_x_mm", "drill_y_mm"])
        for f in sorted(board.GetFootprints(), key=lambda item: item.GetReference()):
            for z in f.Pads():
                if z.GetNumber():
                    thru = z.GetAttribute() == p.PAD_ATTRIB_PTH
                    side = "F.Cu" if z.GetLayerSet().Contains(p.F_Cu) else "B.Cu"
                    assembly = "BOTH" if thru else ("LEFT" if side == "F.Cu" else "RIGHT")
                    if f.GetReference() == "U1":
                        front_y = MCU_F_Y + (-7.6114 if int(z.GetNumber()) <= 12 else 7.6086)
                        assembly = "LEFT" if abs(mm(z.GetPosition())[1] - front_y) < .001 else "RIGHT"
                    writer.writerow([f.GetReference(), z.GetNumber(), z.GetNetname(),
                                     *mm(z.GetPosition()), "F.Cu+B.Cu" if thru else side,
                                     assembly, *mm(z.GetDrillSize())])


def run_cli(*args):
    result = subprocess.run(["kicad-cli", *map(str, args)], capture_output=True, text=True)
    print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    if result.returncode:
        raise RuntimeError(f"KiCad command failed ({result.returncode}): {args}")


def fingerprints():
    result = {label: hashlib.sha256(path.read_bytes()).hexdigest() for label, path in (
        ("board", BOARD), ("schematic", D / (NAME + ".kicad_sch")),
        ("plate", D / (NAME + "-plate.kicad_pcb")))}
    project = json.loads((D / (NAME + ".kicad_pro")).read_text())
    settings = project.get("board", {}).get("design_settings", {})
    rules = {key: settings.get(key, {}) for key in ("rules", "rule_severities", "drc_exclusions")}
    rules["net_settings"] = project.get("net_settings", {})
    result["rules"] = hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()
    return result


def record_checked_inputs():
    (V / "check-inputs.json").write_text(json.dumps(fingerprints(), indent=2), encoding="utf-8")


def checks():
    run_cli("sch", "export", "netlist", "--format", "kicadxml", "-o", V / (NAME + ".xml"),
            D / (NAME + ".kicad_sch"))
    run_cli("sch", "erc", "--format", "json", "-o", V / ("erc-" + NAME + ".json"),
            D / (NAME + ".kicad_sch"))
    run_cli("pcb", "drc", "--schematic-parity", "--format", "json", "-o",
            V / ("drc-" + NAME + ".json"), BOARD)
    run_cli("pcb", "drc", "--format", "json", "-o", V / ("drc-" + NAME + "-plate.json"),
            D / (NAME + "-plate.kicad_pcb"))
    record_checked_inputs()


def import_routing():
    b = p.LoadBoard(str(BOARD))
    assert p.ImportSpecctraSES(b, str(V / (NAME + ".ses")))
    finish(b)


def refresh():
    """Regenerate auxiliary artifacts after editing the routed v3 board."""
    b = p.LoadBoard(str(BOARD))
    mcu = next(f for f in b.GetFootprints() if f.GetReference() == "U1")
    assert str(mcu.GetFPID().GetLibItemName()) == "ProMicro_DualRow"
    for z in mcu.Pads():
        z.SetDrillSize(xy(1, 1))
    finish(b)
    print("Updated v3 headers and regenerated schematic, plate, libraries, and pin table")


def hole_contains(z, point, tolerance=.001):
    """Check a point against the actual round/capsule drill, not copper bounds."""
    px, py = point
    cx, cy = mm(z.GetPosition())
    w, h = mm(z.GetDrillSize())
    if not w or not h:
        return False
    theta = math.radians(z.GetOrientationDegrees())
    dx, dy = px - cx, py - cy
    # Inverse of KiCad's rotation in screen coordinates.
    rx, ry = dx * math.cos(theta) - dy * math.sin(theta), dx * math.sin(theta) + dy * math.cos(theta)
    if w >= h:
        distance = math.hypot(max(abs(rx) - (w - h) / 2, 0), ry)
        radius = h / 2
    else:
        distance = math.hypot(rx, max(abs(ry) - (h - w) / 2, 0))
        radius = w / 2
    return distance <= radius + tolerance


def verify(placement_only=False):
    checked = json.loads((V / "check-inputs.json").read_text())
    assert fingerprints() == checked, "Board, schematic, plate, or design rules changed; rerun checks"
    b = p.LoadBoard(str(BOARD))
    old = archived_board()
    fs = {f.GetReference(): f for f in b.GetFootprints()}
    prior = {f.GetReference(): f for f in old.GetFootprints()}
    solderable_pth = [z for f in b.GetFootprints() for z in f.Pads()
                      if z.GetAttribute() == p.PAD_ATTRIB_PTH]
    assert all(z.GetLayerSet().Contains(p.F_Mask) and z.GetLayerSet().Contains(p.B_Mask)
               for z in solderable_pth), "Through-hole solder mask opening missing"
    assert len(fs) == len(list(b.GetFootprints())), "Duplicate component references"
    expected_mcu = pin_map(prior["U1"])
    assert pin_map(fs["U1"]) == expected_mcu
    assert len(list(fs["U1"].Pads())) == 48
    ox, oy = mm(prior["U1"].GetPosition())
    for old_pad in prior["U1"].Pads():
        px, py = mm(old_pad.GetPosition())
        dx, dy = px - ox, py - oy
        candidates = [z for z in fs["U1"].Pads() if z.GetNumber() == old_pad.GetNumber()]
        assert len(candidates) == 2
        assert all(z.GetDrillSize() == xy(1, 1) for z in candidates)
        for xx, yy in ((MCU_X + dx, MCU_F_Y + dy), (MCU_X + dx, MCU_B_Y - dy)):
            assert sum(abs(mm(z.GetPosition())[0] - xx) < .000003 and
                       abs(mm(z.GetPosition())[1] - yy) < .000003 for z in candidates) == 1
    # Accessories retain their original functional pin assignments.
    assert pin_map(fs["J1"]) == pin_map(prior["J1"])
    assert {k: v for k, v in pin_map(fs["SW_POWER1"]).items() if k != "1"} == {
        k: v for k, v in pin_map(prior["SW_POWER1"]).items() if k != "1"}
    assert pin_map(fs["RSW1"]) == pin_map(prior["RSW1"])
    keys = [f for f in b.GetFootprints() if re.fullmatch(r"SW\d+", f.GetReference())]
    assert len(keys) == 17
    previous_keys = {}
    for f in old.GetFootprints():
        if p.ToMM(f.GetPosition().x) < 133 and "keyswitch_" in str(f.GetFPID().GetLibItemName()):
            name = next(z.GetNetname() for z in f.Pads() if re.fullmatch(r"Switch\d+", z.GetNetname()))
            previous_keys[name] = f
    terminal_checks = drill_checks = 0
    for f in keys:
        number = int(f.GetReference()[2:])
        switch_net = "Switch" + str(number)
        old_key = previous_keys[switch_net]
        assert f.GetPosition() == old_key.GetPosition() and f.GetOrientationDegrees() == 0
        cx, cy = mm(f.GetPosition())
        for family, terminals in SWITCH_TERMINALS.items():
            for face, mirror in (("front", 1), ("back", -1)):
                found = []
                for x, y in terminals:
                    pads = [z for z in f.Pads() if z.GetAttribute() == p.PAD_ATTRIB_PTH and
                            hole_contains(z, (cx + mirror * x, cy + y))]
                    assert pads, (f.GetReference(), family, face, x, y, "Missing terminal drill")
                    nets = {z.GetNetname() for z in pads}
                    assert len(nets) == 1, "Conflicting nets in one physical drill"
                    found.append(next(iter(nets)))
                assert set(found) == {switch_net, "GND"}, (f.GetReference(), family, face, found)
                terminal_checks += 1
        for old_pad in old_key.Pads():
            assert any(hole_contains(z, mm(old_pad.GetPosition())) for z in f.Pads()), (
                "Original switch drill was lost", f.GetReference(), mm(old_pad.GetPosition()))
            drill_checks += 1
        for z in f.Pads():
            x, y = mm(z.GetPosition())
            assert any(abs(mm(a.GetPosition())[0] - (2 * cx - x)) < .000003 and
                       abs(mm(a.GetPosition())[1] - y) < .000003 and
                       a.GetDrillSize() == z.GetDrillSize() for a in f.Pads()), "Asymmetric switch drill"
    # The paired TRRS pads are mechanically mirrored to within 0.04 mm in the
    # inherited footprint; their slots tolerate this and their nets agree.
    j = fs["J1"]
    jx, _ = mm(j.GetPosition())
    for z in j.Pads():
        if z.GetNumber():
            x, y = mm(z.GetPosition())
            assert any(abs(mm(a.GetPosition())[0] - (2 * jx - x)) <= .061 and
                       abs(mm(a.GetPosition())[1] - y) <= .061 and
                       a.GetNetname() == z.GetNetname() for a in j.Pads()), "TRRS face pin mismatch"
    ps = fs["SW_POWER1"]
    pcx, _ = mm(ps.GetPosition())
    for z in ps.Pads():
        if z.GetNumber() and z.GetLayerSet().Contains(p.F_Cu):
            x, y = mm(z.GetPosition())
            assert any(a.GetLayerSet().Contains(p.B_Cu) and a.GetNumber() == z.GetNumber() and
                       a.GetNetname() == z.GetNetname() and
                       abs(mm(a.GetPosition())[0] - (2 * pcx - x)) < .000003 and
                       abs(mm(a.GetPosition())[1] - y) < .000003 for a in ps.Pads())
    # Both module envelopes clear the keycaps and the plate's open component area.
    for center_y in (MCU_F_Y, MCU_B_Y):
        bounds = (MCU_X - 18.375, center_y - 8.975, MCU_X + 14.825, center_y + 8.975)
        assert bounds[0] >= L and bounds[2] <= R and bounds[3] <= BOTTOM
        assert bounds[1] >= 108.25 and bounds[2] <= 92.75
        for f in keys:
            x, y = mm(f.GetPosition())
            assert (bounds[2] <= x - 9 or bounds[0] >= x + 9 or
                    bounds[3] <= y - 9 or bounds[1] >= y + 9), "MCU overlaps a keycap"
    schematic_tree = ET.parse(V / (NAME + ".xml"))
    sch = {(z.get("ref"), z.get("pin")): n.get("name").lstrip("/")
           for n in schematic_tree.findall(".//nets/net") for z in n.findall("node")
           if not n.get("name").startswith("unconnected-")}
    pcb = {(f.GetReference(), z.GetNumber()): z.GetNetname()
           for f in b.GetFootprints() for z in f.Pads() if z.GetNumber() and z.GetNetname()
           and not z.GetNetname().startswith("unconnected-")}
    assert sch == pcb, (sch.items() - pcb.items(), pcb.items() - sch.items())
    if placement_only:
        summary = {"reversible_switch_terminal_checks": terminal_checks,
                   "original_switch_drill_centres_retained": drill_checks,
                   "original_gpio_mapping_preserved_both_faces": True,
                   "original_key_positions_preserved": True,
                   "controller_and_plate_envelopes_clear": True,
                   "schematic_matches_pcb": True}
        (V / "placement-checks.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return
    reports = {}
    for name in ("drc-" + NAME, "drc-" + NAME + "-plate"):
        report = json.loads((V / (name + ".json")).read_text())
        assert not report["violations"] and not report["unconnected_items"], name
        assert not report.get("schematic_parity", []), "PCB/schematic mismatch"
        reports[name] = {"violations": 0, "unconnected_items": 0}
    erc = json.loads((V / ("erc-" + NAME + ".json")).read_text())
    assert all(not sheet["violations"] for sheet in erc["sheets"])
    summary = {
        "project": NAME, "revision": REVISION, "pcb_designs": 1,
        "reversible": True, "board_mm": [95.25, 80], "boards_per_keyboard": 2,
        "keys_per_board": 17, "keys_per_keyboard": 34,
        "controller_mount": "U1 dual row footprint: L rows from F side for left, R rows from B side for right",
        "controller_row_offset_mm": round(MCU_B_Y - MCU_F_Y, 2), "mcu_solder_jumpers": 0,
        "controller_header_drill_mm": 1.0,
        "pth_pads_with_openings_both_masks": len(solderable_pth),
        "original_gpio_mapping_preserved_both_faces": True,
        "original_key_positions_preserved": True,
        "switch_terminal_checks_both_faces": terminal_checks,
        "original_switch_drill_centres_retained": drill_checks,
        "matching_pin_net_assignments": len(pcb), "schematic_matches_pcb": True,
        "schematic_parity_issues": 0, "erc_violations": 0,
        "traces_and_vias": len(list(b.GetTracks())), "kicad_version": p.GetBuildVersion(),
        "board_sha256": hashlib.sha256(BOARD.read_bytes()).hexdigest(),
        "physical_prototype_tested": False, **reports,
    }
    (V / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def prune():
    """Remove only free-ended redundant segments positively identified by DRC."""
    report = json.loads((V / ("drc-" + NAME + ".json")).read_text())
    assert not report["unconnected_items"]
    assert all(v["type"] == "track_dangling" for v in report["violations"])
    ids = {item["uuid"] for v in report["violations"] for item in v["items"]}
    b = p.LoadBoard(str(BOARD))
    removed = 0
    for track in list(b.GetTracks()):
        if track.m_Uuid.AsString() in ids:
            b.Remove(track)
            removed += 1
    assert removed == len(ids), (removed, len(ids))
    p.SaveBoard(str(BOARD), b)
    print("Removed", removed, "DRC-reported redundant track segments")


def clean():
    checked = json.loads((V / "check-inputs.json").read_text())
    assert all(fingerprints()[key] == checked[key] for key in ("schematic", "plate", "rules"))
    for _ in range(20):
        report = json.loads((V / ("drc-" + NAME + ".json")).read_text())
        if not report["violations"]:
            assert not report["unconnected_items"]
            print("PCB DRC: zero violations and zero unconnected items")
            record_checked_inputs()
            return
        prune()
        run_cli("pcb", "drc", "--schematic-parity", "--format", "json", "-o",
                V / ("drc-" + NAME + ".json"), BOARD)
    raise RuntimeError("Too many dangling-track cleanup passes")


def preview():
    """Two assembly views derived from the same finished single-half PCB."""
    import cairosvg
    b = p.LoadBoard(str(BOARD))
    mirror_x = R + L + 107.25
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="216mm" height="104mm" viewBox="28 38 216 104">',
        '<rect x="28" y="38" width="216" height="104" fill="#f2f4f7"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#24334a;text-anchor:middle}</style>',
        f'<text x="136" y="43" font-size="2.4">SweepPluck v{REVISION} - reversible PCB / 34-key split</text>',
    ]
    def text(x, y, value, size=1.6, color="#24334a"):
        elements.append(f'<text x="{x}" y="{y}" font-size="{size}" style="fill:{color}">{html.escape(str(value))}</text>')
    def rect(x, y, width, height, fill, radius=0):
        elements.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" '
                        f'fill="{fill}" stroke="#70818a" stroke-width=".15"/>')
    for back in (False, True):
        transform = (lambda x: mirror_x - x) if back else (lambda x: x)
        origin = mirror_x - R if back else L
        rect(origin, TOP, R - L, BOTTOM - TOP, "#315b55")
        text(origin + (R - L) / 2, 48, "RIGHT / B side" if back else "LEFT / F side", 1.9)
        for f in b.GetFootprints():
            ref = f.GetReference()
            x, y = mm(f.GetPosition())
            x = transform(x)
            if re.fullmatch(r"SW\d+", ref):
                rect(x - 9, y - 9, 18, 18, "#f7f5ee", 1.2)
                text(x, y + 1, ref[2:], 2.4)
            elif ref == "U1":
                y = MCU_B_Y if back else MCU_F_Y
                bx = x - (14.825 if back else 18.375)
                rect(bx, y - 8.975, 33.2, 17.95, "#223b61", .4)
                rect(x + 18.225 if back else x - 21.275, y - 3.825, 3.05, 7.65, "#bbc5cb", .2)
                text(x, y - .7, "Pro Micro", 1.9, "#ffffff")
                text(x, y + 1.5, "FACE DOWN", 1.3, "#c7d8ed")
                text(x, y + 3.6, "U1 / R rows" if back else "U1 / L rows", 1.3, "#c7d8ed")
                for z in f.Pads():
                    px, py = mm(z.GetPosition())
                    num = int(z.GetNumber())
                    selected_y = MCU_B_Y + (7.6114 if num <= 12 else -7.6086) if back else \
                        MCU_F_Y + (-7.6114 if num <= 12 else 7.6086)
                    if abs(py - selected_y) < .001:
                        elements.append(f'<circle cx="{transform(px)}" cy="{py}" r=".65" fill="#e9c76e"/>')
            elif ref == "J1":
                rect(x - 3.125, y - 12.32, 6.255, 14.395, "#3d4150", .4)
                text(x, y - 5, "TRRS", 1.35, "#ffffff")
            elif ref == "SW_POWER1":
                rect(x - 4.15, y - 2.2, 8.3, 4.4, "#d2d9dd", .2)
                text(x, y + .5, "PWR", 1.4)
            elif ref == "RSW1":
                rect(x - 1.7, y - 1.4, 3.4, 2.8, "#d2d9dd", .2)
                text(x, y + 3.8, "RESET", 1.1, "#ffffff")
            elif ref.startswith("BAT"):
                elements.append(f'<circle cx="{x}" cy="{y}" r="1.05" fill="#e9c76e"/>')
                text(x, y + .5, "+" if ref == "BATP1" else "-", 1.6)
            elif ref.startswith("H"):
                elements.append(f'<circle cx="{x}" cy="{y}" r="1.6" fill="#f2f4f7" stroke="#24473f" stroke-width=".15"/>')
        text(origin + (R - L) / 2, 136, "95.25 x 80 mm", 1.8)
    text(136, 140, "Order two identical PCBs; fit one controller per board using the marked rows.", 1.55)
    elements.append("</svg>")
    svg = "\n".join(elements)
    (D / (NAME + "-layout.svg")).write_text(svg, encoding="utf-8")
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(D / (NAME + "-preview.png")), output_width=2160)
    print("Generated left/front and right/back assembly views from one PCB")


def export():
    verify()
    gerbers = D / "gerbers"
    gerbers.mkdir(exist_ok=True)
    stage = V / "gerber-export"
    stage.mkdir(exist_ok=True)
    for file in stage.iterdir():
        assert file.is_file() and file.name.startswith(NAME), "Unexpected file in Gerber staging folder"
        file.unlink()
    run_cli("pcb", "export", "gerbers", "-l", "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts",
            "--no-x2", "--no-netlist", "--disable-aperture-macros", "--subtract-soldermask",
            "--use-drill-file-origin",
            "-o", str(stage) + "/", BOARD)
    run_cli("pcb", "export", "drill", "--excellon-separate-th", "--drill-origin", "plot",
            "--excellon-units", "mm", "--excellon-zeros-format", "decimal",
            "--excellon-oval-format", "alternate", "-o", str(stage) + "/", BOARD)
    produced = sorted(stage.iterdir())
    assert all(file.is_file() and file.stat().st_size for file in produced)
    assert {file.suffix for file in produced} == {".gtl", ".gbl", ".gts", ".gbs", ".gto", ".gbo", ".gm1", ".drl", ".gbrjob"}
    assert len(produced) == 10
    with ZipFile(D / "archive" / "SweepPluck-v2-panel.zip") as archive:
        previous = {Path(n).name for n in archive.namelist() if n.startswith("gerbers/")}
    for file in gerbers.iterdir():
        if file.is_file() and file.name in previous:
            file.unlink()
    for file in produced:
        (gerbers / file.name).write_bytes(file.read_bytes())
    run_cli("pcb", "export", "dxf", "--layers", "Edge.Cuts", "--mode-single", "--output-units", "mm", "-o",
            D / (NAME + "-plate.dxf"), D / (NAME + "-plate.kicad_pcb"))
    run_cli("pcb", "export", "svg", "--layers", "F.Cu,F.Mask,F.Silkscreen,Edge.Cuts", "--page-size-mode", "2", "--exclude-drawing-sheet",
            "--mode-single", "-o", D / (NAME + "-preview.svg"), BOARD)
    run_cli("pcb", "export", "svg", "--layers", "B.Cu,B.Mask,B.Silkscreen,Edge.Cuts", "--page-size-mode", "2", "--exclude-drawing-sheet",
            "--mode-single", "--mirror", "-o", D / (NAME + "-back.svg"), BOARD)
    run_cli("pcb", "export", "svg", "--layers", "Edge.Cuts", "--page-size-mode", "2", "--black-and-white", "--exclude-drawing-sheet",
            "--mode-single", "-o", D / (NAME + "-plate.svg"), D / (NAME + "-plate.kicad_pcb"))
    import cairosvg
    for suffix in ("-preview", "-back", "-plate"):
        cairosvg.svg2png(url=str(D / (NAME + suffix + ".svg")),
                        write_to=str(D / (NAME + suffix + "-pcb.png")), output_width=1800,
                        background_color="#ffffff")
    upload_names = {
        NAME + "-F_Cu.gtl": "TopCopper.GTL", NAME + "-B_Cu.gbl": "BottomCopper.GBL",
        NAME + "-F_Mask.gts": "TopSolderMask.GTS", NAME + "-B_Mask.gbs": "BottomSolderMask.GBS",
        NAME + "-F_Silkscreen.gto": "TopSilkscreen.GTO", NAME + "-B_Silkscreen.gbo": "BottomSilkscreen.GBO",
        NAME + "-Edge_Cuts.gm1": "BoardOutline.GKO", NAME + "-PTH.drl": "Plated.DRL",
        NAME + "-NPTH.drl": "NonPlated.DRL",
    }
    with ZipFile(D / (NAME + "-gerbers.zip"), "w", ZIP_DEFLATED) as z:
        for file in produced:
            if file.name in upload_names:
                z.write(file, upload_names[file.name])
    (D / (NAME + "-JLCPCB.zip")).write_bytes((D / (NAME + "-gerbers.zip")).read_bytes())
    preview()
    summary_path = V / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["manufacturing_files"] = {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in produced}
    summary["upload_file_hashes"] = {upload_names[file.name]: hashlib.sha256(file.read_bytes()).hexdigest()
                                      for file in produced if file.name in upload_names}
    summary["upload_format"] = "RS-274X without X2/netlist/macros; Protel extensions; Excellon decimal mm; positive plot coordinates"
    summary["gerber_zip_sha256"] = hashlib.sha256((D / (NAME + "-gerbers.zip")).read_bytes()).hexdigest()
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def route(jar):
    """Route all net connections; keep process output in the project report."""
    session = V / (NAME + ".ses")
    if session.exists():
        session.unlink()
    command = ["java", "-Xmx3g", "-Djava.awt.headless=true", "-jar", str(jar),
               "-de", str(V / (NAME + ".dsn")), "-do", str(V / (NAME + ".ses")),
               "-mp", "12", "-mt", "1"]
    with (V / "routing.log").open("w") as log:
        result = subprocess.run(command, cwd=str(V), stdout=log, stderr=subprocess.STDOUT)
    assert result.returncode == 0, "Freerouting failed; see verification/routing.log"
    assert (V / (NAME + ".ses")).exists()
    print("Routing session saved")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "import", "refresh", "checks", "placement", "verify", "prune", "clean", "preview", "export", "route"])
    parser.add_argument("--jar", type=Path)
    args = parser.parse_args()
    if args.command == "route":
        assert args.jar and args.jar.is_file(), "Provide --jar path/to/freerouting-2.1.0.jar"
        route(args.jar)
    elif args.command == "placement":
        verify(placement_only=True)
    else:
        {"build": build, "import": import_routing, "refresh": refresh, "checks": checks, "verify": verify,
         "prune": prune, "clean": clean, "preview": preview, "export": export}[args.command]()


if __name__ == "__main__":
    main()
