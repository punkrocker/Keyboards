from pathlib import Path
import pcbnew as p
D=Path(__file__).resolve().parents[1]
def xy(x,y): return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def line(b,a,c):
    s=p.PCB_SHAPE(); s.SetShape(p.SHAPE_T_SEGMENT); s.SetStart(xy(*a)); s.SetEnd(xy(*c)); s.SetLayer(p.Edge_Cuts); s.SetWidth(p.FromMM(.05)); b.Add(s)
def polygon(b,points):
    for i,a in enumerate(points): line(b,a,points[(i+1)%len(points)])
for name in ['SweepPluck','SweepPluck-right']:
    source=p.LoadBoard(str(D/(name+'.kicad_pcb'))); plate=p.BOARD(); right=name.endswith('right')
    if right: points=[(150,48),(266.6,48),(266.6,140),(150,140),(150,126),(171,126),(171,62),(150,62)]
    else: points=[(34,48),(150.6,48),(150.6,62),(130,62),(130,126),(150.6,126),(150.6,140),(34,140)]
    polygon(plate,points)
    for f in source.GetFootprints():
        x=p.ToMM(f.GetPosition().x); y=p.ToMM(f.GetPosition().y)
        if 'keyswitch_' in str(f.GetFPID().GetLibItemName()): polygon(plate,[(x-7,y-7),(x+7,y-7),(x+7,y+7),(x-7,y+7)])
        elif f.GetReference().startswith('H'):
            c=p.PCB_SHAPE(); c.SetShape(p.SHAPE_T_CIRCLE); c.SetCenter(xy(x,y)); c.SetEnd(xy(x+1.6,y)); c.SetLayer(p.Edge_Cuts); c.SetWidth(p.FromMM(.05)); plate.Add(c)
    p.SaveBoard(str(D/(name+'-plate.kicad_pcb')),plate)
