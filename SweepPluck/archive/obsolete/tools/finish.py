"""Finish routed boards, generate modern self-contained schematics, and verify pin maps."""
from pathlib import Path
import uuid, json, re, csv
import pcbnew as p

D=Path(__file__).resolve().parents[1]
def uid(): return str(uuid.uuid4())
def q(s): return json.dumps(str(s),ensure_ascii=False)
def fx(size=1): return f'(effects (font (size {size} {size})))'
def schematic(b,name):
    root=uid(); libs=[]; instances=[]; labels=[]; assignments=[]
    for i,f in enumerate(sorted(b.GetFootprints(),key=lambda f:f.GetReference())):
        pads={pad.GetNumber():pad.GetNetname() for pad in f.Pads() if pad.GetNumber() and pad.GetAttribute()!=p.PAD_ATTRIB_NPTH}
        if not pads: continue
        symbol=name+':P'+str(i); x=30.48+(i%5)*76.2; y=25.4+(i//5)*35.56
        if len(pads)>10: x,y=30.48,215.9
        n=len(pads); h=(n+1)*2.54; ref=f.GetReference(); val=f.GetValue(); fp=f'SweepPluck:{f.GetFPID().GetLibItemName()}'
        props=f'(property "Reference" {q(ref)} (at 0 3 0) {fx()}) (property "Value" {q(val)} (at 0 0 0) {fx()}) (property "Footprint" {q(fp)} (at 0 0 0) {fx()} (hide yes))'
        pins=' '.join(f'(pin passive line (at -11.43 {-2.54*(j+1):.4f} 0) (length 5.08) (name {q(num)} {fx(.8)}) (number {q(num)} {fx(.8)}))' for j,num in enumerate(pads))
        libs.append(f'(symbol {q(symbol)} (pin_names (offset 0)) (in_bom yes) (on_board yes) {props} (symbol "P{i}_0_1" (rectangle (start -6.35 0) (end 6.35 {-h:.4f}) (stroke (width .254) (type default)) (fill (type background)))) (symbol "P{i}_1_1" {pins}))')
        instance=uid()
        iprops=f'(property "Reference" {q(ref)} (at {x} {y-3} 0) {fx()}) (property "Value" {q(val)} (at {x} {y} 0) {fx()}) (property "Footprint" {q(fp)} (at {x} {y} 0) {fx()} (hide yes))'
        instances.append(f'(symbol (lib_id {q(symbol)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {instance}) {iprops} '+ ' '.join(f'(pin {q(num)} (uuid {uid()}))' for num in pads) + f' (instances (project {q(name)} (path "/{root}" (reference {q(ref)}) (unit 1)))))')
        for j,(num,net) in enumerate(pads.items()):
            yy=y+(j+1)*2.54; xx=x-11.43
            if net: labels.append(f'(label {q(net)} (at {xx:.4f} {yy:.4f} 0) {fx(.8)} (uuid {uid()}))')
            else: labels.append(f'(no_connect (at {xx:.4f} {yy:.4f}) (uuid {uid()}))')
            assignments.append((ref,num,net))
    result=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {root}) (paper "A3") (title_block (title "{name} direct pin wiring") (rev "1.0")) (lib_symbols '+ '\n'.join(libs)+')\n'+'\n'.join(labels+instances)+' (sheet_instances (path "/" (page "1"))))\n'
    (D/(name+'.kicad_sch')).write_text(result,encoding='utf-8')
    # Symbols may skip the two mechanical holes, so use each actual symbol ID.
    library='\n'.join(re.sub(r'^\(symbol "'+re.escape(name)+r':', '(symbol "', s, count=1) for s in libs)
    (D/(name+'.kicad_sym')).write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+library+'\n)',encoding='utf-8')
    return assignments

if __name__=='__main__':
    for name in ['SweepPluck','SweepPluck-right']:
        path=D/(name+'.kicad_pcb'); source=path.read_text(encoding='utf-8')
        # Remove the redundant unconnected round pad before loading (KiCad 10
        # Python's Remove() invalidates SWIG vector conversions on this build).
        cuts=[]
        for m in re.finditer(r'\(pad\s+""\s+np_thru_hole',source):
            depth=0
            for end in range(m.start(),len(source)):
                if source[end]=='(': depth+=1
                elif source[end]==')':
                    depth-=1
                    if depth==0: break
            chunk=source[m.start():end+1]
            if re.search(r'\(at -?5\.5 0(?:\s|\))',chunk): cuts.append((m.start(),end+1))
        for a,z in reversed(cuts): source=source[:a]+source[z:]
        path.write_text(source,encoding='utf-8'); b=p.LoadBoard(str(path))
        # Move inherited tiny labels off the solder pads; keep readable board name.
        for f in b.GetFootprints():
            if 'SPDT' in str(f.GetFPID().GetLibItemName()):
                for pad in f.Pads():
                    if pad.GetNumber()=='1': pad.SetNetCode(0)
            if 'keyswitch_' in str(f.GetFPID().GetLibItemName()):
                # Source's overlapping MX/Choc locating holes become one plated-free slot.
                # 2.17 x 1.8 fully encloses the original 1.7 and 1.8 mm holes.
                for sign in [-1,1]:
                    holes=[z for z in f.Pads() if z.GetAttribute()==p.PAD_ATTRIB_NPTH and abs(p.ToMM(z.GetFPRelativePosition().x)-sign*5.08)<.01]
                    if holes:
                        z=holes[0]; z.SetFPRelativePosition(p.VECTOR2I(p.FromMM(sign*5.315),0)); z.SetPosition(f.GetPosition()+z.GetFPRelativePosition()); z.SetOrientationDegrees(0)
                        z.SetShape(p.PAD_SHAPE_OVAL); z.SetSize(p.VECTOR2I(p.FromMM(2.17),p.FromMM(1.8))); z.SetDrillShape(p.PAD_DRILL_SHAPE_OBLONG); z.SetDrillSize(z.GetSize())
            for t in [f.Reference(),f.Value()]: t.SetVisible(False)
            for g in f.GraphicalItems():
                if g.GetLayer() in [p.F_SilkS,p.B_SilkS]: g.SetLayer(p.F_Fab if g.GetLayer()==p.F_SilkS else p.B_Fab)
        schematic(b,name)
        p.SaveBoard(str(D/(name+'.kicad_pcb')),b)
        with (D/(name+'-pins.csv')).open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.writer(stream); writer.writerow(['reference','pad','net','x_mm','y_mm'])
            for f in sorted(b.GetFootprints(),key=lambda f:f.GetReference()):
                for pad in f.Pads():
                    if pad.GetNumber(): writer.writerow([f.GetReference(),pad.GetNumber(),pad.GetNetname(),p.ToMM(pad.GetPosition().x),p.ToMM(pad.GetPosition().y)])
        for f in b.GetFootprints(): p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(D/'SweepPluck.pretty'),f)
        (D/(name+'.kicad_pro')).write_text(json.dumps({'meta':{'filename':name+'.kicad_pro','version':1},'board':{'design_settings':{'rules':{'min_clearance':.2,'min_copper_edge_clearance':.25,'min_track_width':.2,'min_via_diameter':.6,'min_through_hole_diameter':.3}}},'net_settings':{'classes':[{'name':'Default','clearance':.2,'track_width':.25,'via_diameter':.6,'via_drill':.3}],'version':3}},indent=2))
        print(name,'tracks',len(list(b.GetTracks())))
    (D/'sym-lib-table').write_text('(sym_lib_table (version 7) '+ ' '.join(f'(lib (name "{n}")(type "KiCad")(uri "${{KIPRJMOD}}/{n}.kicad_sym")(options "")(descr "Direct pin symbols"))' for n in ['SweepPluck','SweepPluck-right'])+')\n',encoding='utf-8')


