"""Generate ortholinear SweepPluck from the embedded Sweep High footprints.
Run with KiCad's bundled Python from the repository root.
"""
from pathlib import Path
import json, csv
import pcbnew as p

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'SweepPluck'
SOURCE = ROOT / 'Sweep High' / 'sweep-high.kicad_pcb'
def clean_source():
    s=SOURCE.read_text(encoding='utf-8'); chunks=[]; depth=0; quoted=False; escaped=False; start=0
    for i,c in enumerate(s):
        if quoted:
            if escaped: escaped=False
            elif c=='\\': escaped=True
            elif c=='"': quoted=False
            continue
        if c=='"': quoted=True
        elif c=='(':
            depth+=1
            if depth==2: start=i
        elif c==')':
            if depth==2:
                chunk=s[start:i+1]; kind=chunk[1:].split()[0]
                if kind not in ['segment','via','zone'] and not kind.startswith('gr_'): chunks.append(chunk)
            depth-=1
    target=OUT/'verification'/'source-footprints.kicad_pcb'
    target.write_text('(kicad_pcb\n'+'\n'.join(chunks)+'\n)\n',encoding='utf-8')
    return target
def xy(x,y): return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def pos(f): return (p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y))
def edge(b,x1,y1,x2,y2):
    s=p.PCB_SHAPE(); s.SetShape(p.SHAPE_T_SEGMENT); s.SetStart(xy(x1,y1)); s.SetEnd(xy(x2,y2)); s.SetLayer(p.Edge_Cuts); s.SetWidth(p.FromMM(.05)); b.Add(s)
def rect(b,x1,y1,x2,y2):
    for a,c in [((x1,y1),(x2,y1)),((x2,y1),(x2,y2)),((x2,y2),(x1,y2)),((x1,y2),(x1,y1))]: edge(b,*a,*c)

def schematic(b,name):
    # Passive connector symbols expose the PCB's actual pad-number/net mapping.
    lib=['EESchema-LIBRARY Version 2.4','']
    sch=['EESchema Schematic File Version 4','EELAYER 30 0','EELAYER END', '$Descr A3 16535 11693','encoding utf-8','Sheet 1 1',f'Title "SweepPluck {name} - direct pin wiring"','Rev "1.0"','$EndDescr']
    for i,f in enumerate(sorted(b.GetFootprints(),key=lambda f:f.GetReference())):
        pads={q.GetNumber():q.GetNetname() for q in f.Pads() if q.GetNumber() and q.GetAttribute()!=p.PAD_ATTRIB_NPTH}
        if not pads: continue
        sym='P'+str(i); n=len(pads); h=(n+1)*100
        lib += [f'# {sym}',f'DEF {sym} J 0 40 Y Y 1 F N',f'F0 "J" 0 100 50 H V C CNN',f'F1 "{sym}" 0 0 50 H V C CNN','DRAW',f'S -250 0 250 -{h} 0 1 10 f']
        for j,(num,net) in enumerate(pads.items()): lib += [f'X {num} {num} -450 -{(j+1)*100} 200 R 40 40 1 1 P']
        lib += ['ENDDRAW','ENDDEF','']
        x=1300+(i%5)*2900; y=650+(i//5)*1500
        # MCU requires taller panel; put it in reserved bottom area.
        if n>10: x,y=1300,7800
        fid=str(f.GetFPID().GetLibItemName())
        sch += ['$Comp',f'L SweepPluck:{sym} {f.GetReference()}',f'U 1 1 {i+1:08X}',f'P {x} {y}',f'F 0 "{f.GetReference()}" H {x} {y+100} 50 0000 C CNN',f'F 1 "{f.GetValue()}" H {x} {y} 50 0000 C CNN',f'F 2 "SweepPluck:{fid}" H {x} {y} 50 0001 C CNN',f'F 3 "" H {x} {y} 50 0001 C CNN',f'\t1 {x} {y}','\t1 0 0 -1','$EndComp']
        for j,(num,net) in enumerate(pads.items()):
            yy=y+(j+1)*100
            if net:
                sch += ['Wire Wire Line',f'\t{x-450} {yy} {x-800} {yy}',f'Text Label {x-800} {yy} 2 35 ~ 0',net]
            else: sch += [f'NoConn ~ {x-450} {yy}']
    lib += ['#End Library']; sch+=['$EndSCHEMATC']
    (OUT/'SweepPluck.lib').write_text('\n'.join(lib)+'\n')
    (OUT/(name+'.sch')).write_text('\n'.join(sch)+'\n')

def build(side):
    b=p.LoadBoard(str(clean_source())); right=side=='right'; name='SweepPluck'+('-right' if right else '')
    fs=list(b.GetFootprints()); keys=[f for f in fs if 'keyswitch_' in str(f.GetFPID().GetLibItemName()) and (pos(f)[0]>150)==right]
    keep=list(keys)
    for f in fs:
        r=f.GetReference(); fid=str(f.GetFPID().GetLibItemName())
        nets={q.GetNetname() for q in f.Pads()}
        if r==('U2' if right else 'U1'): keep.append(f)
        if r==('J1' if right else 'J2'): keep.append(f); f.SetReference('J2' if right else 'J1')
        if r==('RSW2' if right else 'RSW1') and f.GetLayer()==p.B_Cu: keep.append(f); f.SetPosition(xy(160.5 if right else 140,133))
        if 'SPDT' in fid and f.GetLayer()==p.B_Cu and ('BT+_r' if right else 'BT+') in nets:
            keep.append(f); f.SetPosition(xy(160.5 if right else 140,77))
        if fid=='1pin_conn' and (('BT+_r' if right else 'BT+') in nets or (r=='B-' and (pos(f)[0]>150)==right)):
            keep.append(f); f.SetReference(('BATP2' if right else 'BATP1') if r=='B+' else ('BATG2' if right else 'BATG1'))
            f.SetPosition(xy((166 if right else 135) if r=='B+' else (155 if right else 145),68))
    for f in fs:
        if f not in keep: b.Remove(f)
    main=[f for f in keys if not f.GetReference().startswith(('SW20','SW21'))]
    cols=sorted(set(round(pos(f)[0]) for f in main))
    for col in cols:
        colkeys=sorted([f for f in main if round(pos(f)[0])==col],key=lambda f:pos(f)[1])
        for row,f in enumerate(colkeys): f.SetPosition(xy((179.4 if right else 45)+19.05*cols.index(col),60+19.05*row)); f.SetOrientationDegrees(0)
    thumbs=sorted([f for f in keys if f not in main],key=lambda f:pos(f)[0])
    for i,f in enumerate(thumbs): f.SetOrientationDegrees(0); f.SetPosition(xy((179.4 if right else 102.15)+i*19.05,117.15))
    bounds=(150,48,266.6,140) if right else (34,48,150.6,140)
    rect(b,*bounds)
    # Mechanical mounting holes in the empty lower outer area.
    for i,x in enumerate(([227.5,255.6] if right else [45,73.1])):
        f=p.FOOTPRINT(b); f.SetReference(f'H{3+i if right else 1+i}'); f.SetValue('MountingHole_3.2mm'); f.SetPosition(xy(x,130))
        pad=p.PAD(f); pad.SetAttribute(p.PAD_ATTRIB_NPTH); pad.SetShape(p.PAD_SHAPE_CIRCLE); pad.SetSize(xy(3.2,3.2)); pad.SetDrillSize(xy(3.2,3.2)); pad.SetLayerSet(p.LSET.AllCuMask()); f.Add(pad); b.Add(f)
    text=p.PCB_TEXT(b); text.SetText('SweepPluck '+side+' 34-key ortho'); text.SetPosition(xy(211 if right else 89,136)); text.SetTextSize(xy(1,1)); text.SetTextThickness(p.FromMM(.15)); text.SetLayer(p.F_SilkS); b.Add(text)
    # Add copper/mask on both sides to the inherited solder switch pads.
    for f in keys:
        for q in f.Pads():
            if q.GetAttribute()==p.PAD_ATTRIB_PTH:
                layers=q.GetLayerSet(); layers.AddLayer(p.F_Mask); layers.AddLayer(p.B_Mask); q.SetLayerSet(layers)
    libdir=OUT/'SweepPluck.pretty'; libdir.mkdir(exist_ok=True)
    for f in b.GetFootprints():
        fid=str(f.GetFPID().GetLibItemName()) or str(f.GetValue())
        f.SetFPID(p.LIB_ID('SweepPluck',fid)); p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(libdir),f)
    p.SaveBoard(str(OUT/(name+'.kicad_pcb')),b)
    schematic(b,name)
    # DSN export excludes old zones/tracks and routes every net from scratch.
    assert p.ExportSpecctraDSN(b,str(OUT/'verification'/(name+'.dsn')))
    plate=p.BOARD(); rect(plate,*bounds)
    for f in keys:
        x,y=pos(f); rect(plate,x-7,y-7,x+7,y+7)
    for f in b.GetFootprints():
        if f.GetReference().startswith('H'):
            c=p.PCB_SHAPE(); c.SetShape(p.SHAPE_T_CIRCLE); c.SetCenter(f.GetPosition()); c.SetEnd(f.GetPosition()+xy(1.6,0)); c.SetLayer(p.Edge_Cuts); c.SetWidth(p.FromMM(.05)); plate.Add(c)
    p.SaveBoard(str(OUT/(name+'-plate.kicad_pcb')),plate)
    with (OUT/(name+'-pins.csv')).open('w',newline='',encoding='utf-8-sig') as stream:
        w=csv.writer(stream); w.writerow(['reference','pad','net','x_mm','y_mm'])
        for f in sorted(b.GetFootprints(),key=lambda f:f.GetReference()):
            for q in f.Pads():
                if q.GetNumber(): w.writerow([f.GetReference(),q.GetNumber(),q.GetNetname(),*pos(q)])
    print(name,len(keys),'keys')

if __name__=='__main__':
    for side in ['left','right']: build(side)
    (OUT/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "SweepPluck")(type "KiCad")(uri "${KIPRJMOD}/SweepPluck.pretty")(options "")(descr "Embedded Sweep High compatible footprints")))\n')
    (OUT/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "SweepPluck")(type "Legacy")(uri "${KIPRJMOD}/SweepPluck.lib")(options "")(descr "Direct pin netlist symbols")))\n')


