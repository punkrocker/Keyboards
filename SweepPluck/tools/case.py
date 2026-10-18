"""Generate printable enclosure geometry directly from the current KiCad board.
Dependencies: numpy shapely trimesh manifold3d sexpdata mapbox-earcut matplotlib.
Run: python SweepPluck/tools/case.py (from the Sweep repository).
"""
from pathlib import Path
import hashlib, json, zipfile
import xml.etree.ElementTree as ET
import numpy as np
import sexpdata
import trimesh as tm
from shapely.geometry import box, Point, Polygon
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

D = Path(__file__).resolve().parents[1]
OUT = D / 'case'
OUT.mkdir(exist_ok=True)
BOARD = D / 'SweepPluck.kicad_pcb'
def field(n, key):
    return next((v for v in n if isinstance(v, list) and v and str(v[0]) == key), None)
b = sexpdata.loads(BOARD.read_text(encoding='utf-8'))
fps = {field(f, 'property')[2]: f for f in b if isinstance(f, list) and f and str(f[0]) == 'footprint'}
edges = [f for f in b if isinstance(f, list) and f and str(f[0]) == 'gr_line' and field(f, 'layer')[1] == 'Edge.Cuts']
coords = np.array([field(e, k)[1:3] for e in edges for k in ('start', 'end')], float)
origin = coords.min(axis=0)
W, H = coords.max(axis=0) - origin
def pos(ref):
    p = np.array(field(fps[ref], 'at')[1:3], float) - origin
    return np.array([p[0], H-p[1]])  # model rear/top is positive Y
holes = [pos('H1'), pos('H2')]
keys = [pos('SW'+str(i)) for i in range(1, 18)]
CLEAR, WALL, FLOOR, SEAT, HEIGHT = .30, 2.4, 2., 8., 9.2
PILOT = 2.6

def extrude(poly, h, z=0):
    mesh = tm.creation.extrude_polygon(poly, h, engine='earcut')
    mesh.apply_translation([0, 0, z])
    return mesh
def cylinder(x, y, r, z, h):
    return extrude(Point(x,y).buffer(r, quad_segs=32), h, z)
def union(parts):
    return tm.boolean.union(parts, engine='manifold')
def subtract(a, parts):
    return tm.boolean.difference([a]+parts, engine='manifold')
def mirrored(mesh):
    m = mesh.copy()
    t = np.eye(4); t[0,0] = -1; t[0,3] = W
    m.apply_transform(t)
    return m

inner = box(-CLEAR,-CLEAR,W+CLEAR,H+CLEAR)
outer = box(-CLEAR-WALL+3.2,-CLEAR-WALL+3.2,W+CLEAR+WALL-3.2,H+CLEAR+WALL-3.2).buffer(3.2, quad_segs=24)
shell = union([extrude(outer,FLOOR), extrude(outer.difference(inner),HEIGHT-FLOOR,FLOOR),
               *[cylinder(x,y,3.2,FLOOR-.1,SEAT-FLOOR+.1) for x,y in holes]])
# Generous open notches below the board; actual connectors are above the PCB.
# USB at outer left, TRRS at the front edge, mirrored for the right hand.
usb = extrude(box(-8,-3,1,26),20,3.5)
jackx = pos('J1')[0]
trrs = extrude(box(jackx-8,-8,jackx+8,1),20,3.5)
shell = subtract(shell,[usb,trrs,*[cylinder(x,y,PILOT/2,2.5,10) for x,y in holes]])
shells = {'left_tray':shell, 'right_tray':mirrored(shell)}

# Optional switch plate follows the repository's existing plate outline exactly.
platepath = D / 'SweepPluck-plate.kicad_pcb'
pb = sexpdata.loads(platepath.read_text(encoding='utf-8'))
pe = [f for f in pb if isinstance(f,list) and f and str(f[0]).startswith('gr_') and field(f,'layer') and field(f,'layer')[1]=='Edge.Cuts']
# The original outline is documented by the generator. Assert its vertices exist.
verts = [(0,H),(W,H),(W,0),(93-origin[0],0),(93-origin[0],H-(108-origin[1])),(0,H-(108-origin[1]))]
assert all(any(np.allclose(np.array(field(e,k)[1:3],float)-origin,[x,H-y]) for e in pe if str(e[0])=='gr_line' for k in ('start','end')) for x,y in verts)
platepoly = Polygon(verts)
for x,y in keys: platepoly = platepoly.difference(box(x-7,y-7,x+7,y+7))
for x,y in holes: platepoly = platepoly.difference(Point(x,y).buffer(1.6,quad_segs=32))
plate = extrude(platepoly,1.6)
plates = {'left_plate_optional':plate, 'right_plate_optional':mirrored(plate)}
coupon = subtract(union([extrude(box(-9,-9,9,9),2),cylinder(0,0,3.2,1.9,6.1)]),[cylinder(0,0,1.3,2.5,10)])

def normalize(m):
    m=m.copy(); m.apply_translation(-m.bounds[0]); return m
allparts = {**shells, **plates, 'screw_fit_coupon':coupon}
report = {'pcb_sha256':hashlib.sha256(BOARD.read_bytes()).hexdigest(), 'plate_sha256':hashlib.sha256(platepath.read_bytes()).hexdigest(),
          'pcb_mm':[W,H,1.6], 'pcb_origin_kicad_mm':origin.tolist(), 'holes_model_mm':[p.tolist() for p in holes],
          'parameters_mm':{'clearance_each_side':CLEAR,'wall':WALL,'floor':FLOOR,'pcb_underside_z':SEAT,'wall_top':HEIGHT,'pilot_diameter':PILOT},'parts':{}}
for name,m in allparts.items():
    n=normalize(m)
    assert n.is_watertight and n.is_winding_consistent and n.volume>0 and len(n.split())==1, name
    assert np.all(n.extents < [256,256,256])
    n.export(OUT/(name+'.stl'))
    report['parts'][name]={'size_mm':n.extents.tolist(),'watertight':bool(n.is_watertight),'connected_components':len(n.split()),'volume_mm3':float(n.volume),'triangles':len(n.faces)}

def write3mf(path, parts):
    ns='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
    ET.register_namespace('',ns)
    root=ET.Element('{'+ns+'}model',unit='millimeter',attrib={'xml:lang':'en-US'})
    res=ET.SubElement(root,'resources'); build=ET.SubElement(root,'build')
    for i,(name,m,x,y) in enumerate(parts,1):
        m=normalize(m)
        obj=ET.SubElement(res,'object',id=str(i),type='model',name=name)
        mesh=ET.SubElement(obj,'mesh'); vs=ET.SubElement(mesh,'vertices'); ts=ET.SubElement(mesh,'triangles')
        for v in m.vertices: ET.SubElement(vs,'vertex',**dict(zip(('x','y','z'),(f'{a:.6f}' for a in v))))
        for f in m.faces: ET.SubElement(ts,'triangle',**dict(zip(('v1','v2','v3'),map(str,f))))
        ET.SubElement(build,'item',objectid=str(i),transform=f'1 0 0 0 1 0 0 0 1 {x} {y} 0')
        assert x+m.extents[0]<256 and y+m.extents[1]<256
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model',ET.tostring(root,encoding='utf-8',xml_declaration=True))
write3mf(OUT/'SweepPluck_trays_P2S.3mf',[(n,m,15+i*115,85) for i,(n,m) in enumerate(shells.items())])
write3mf(OUT/'SweepPluck_plates_optional.3mf',[(n,m,15+i*115,85) for i,(n,m) in enumerate(plates.items())])

def drawmesh(ax,m,color,alpha=1):
    ax._parts.append((m,color))
    light=matplotlib.colors.LightSource(azdeg=310,altdeg=50)
    intensity=.45+.55*np.maximum(0,m.face_normals @ light.direction)
    colors=np.tile(matplotlib.colors.to_rgba(color),(len(m.faces),1))
    colors[:,:3]*=intensity[:,None]
    coll=Poly3DCollection(m.triangles,facecolors=colors,edgecolors='none',alpha=alpha)
    ax.add_collection3d(coll)
def setup(ax,title):
    ax._parts=[]
    ax.set(xlim=(-8,215),ylim=(-8,90),zlim=(0,65),title=title)
    ax.set_box_aspect((223,98,65)); ax.view_init(42,-65); ax.set_axis_off()
def rasterize(ax):
    # Per-pixel depth avoids matplotlib's painter-order artifacts on long faces.
    parts=ax._parts; fig=ax.figure; title=ax.get_title(); ax.remove()
    right=np.array([.94,.342,0]); up=np.array([-.22,.605,.765]); depth=np.cross(right,up)
    basis=np.array([right,up,depth]).T
    projected=np.concatenate([m.vertices@basis for m,c in parts])
    low=projected[:,:2].min(axis=0); high=projected[:,:2].max(axis=0)
    width,height=1600,780
    scale=min((width-80)/(high[0]-low[0]),(height-60)/(high[1]-low[1]))
    center=(high+low)/2
    rgb=np.full((height,width,3),[244,246,248],dtype=np.uint8)
    zb=np.full((height,width),-np.inf)
    light=np.array([-.4,-.5,.77]); light/=np.linalg.norm(light)
    for mesh,color in parts:
        v=mesh.vertices@basis; v[:,:2]=(v[:,:2]-center)*scale+[width/2,height/2]
        colors=np.array(matplotlib.colors.to_rgb(color))
        shade=.50+.50*np.maximum(0,mesh.face_normals@light)
        for idx,f in enumerate(mesh.faces):
            a,b,c=v[f]; xmin=max(0,int(np.floor(min(a[0],b[0],c[0])))); xmax=min(width-1,int(np.ceil(max(a[0],b[0],c[0]))))
            ymin=max(0,int(np.floor(min(a[1],b[1],c[1])))); ymax=min(height-1,int(np.ceil(max(a[1],b[1],c[1]))))
            den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-9 or xmax<xmin or ymax<ymin: continue
            yy,xx=np.mgrid[ymin:ymax+1,xmin:xmax+1]; xx=xx+.5; yy=yy+.5
            u=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
            vv=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den
            w=1-u-vv; z=u*a[2]+vv*b[2]+w*c[2]
            sub=zb[ymin:ymax+1,xmin:xmax+1]
            mask=(u>=-1e-7)&(vv>=-1e-7)&(w>=-1e-7)&(z>sub)
            sub[mask]=z[mask]; rgb[ymin:ymax+1,xmin:xmax+1][mask]=np.clip(colors*shade[idx]*255,0,255).astype(np.uint8)
    ax2=fig.add_axes([.04,.19,.92,.69]); ax2.imshow(rgb,origin='lower'); ax2.axis('off'); ax2.set_title(title,pad=18,fontsize=15)
fig=plt.figure(figsize=(14,8),facecolor='#f4f6f8')
ax=fig.add_subplot(111,projection='3d'); setup(ax,'SweepPluck v3.1 | mirrored printable trays')
for i,(n,m) in enumerate(shells.items()):
    m=m.copy(); m.apply_translation([i*112,0,0]); drawmesh(ax,m,'#355772')
    ax.text(i*112+W/2, H+4, 0, 'LEFT' if i==0 else 'RIGHT',ha='center',color='#23374a')
fig.text(.12,.09,'100.65 x 85.40 x 9.20 mm each | 0.30 mm PCB clearance per side\n2.0 mm floor | 6.0 mm solder clearance | M3 pilot bosses | USB / TRRS low notches',fontsize=12,color='#23374a')
rasterize(ax); fig.savefig(OUT/'preview_trays.png',dpi=180); plt.close(fig)
fig=plt.figure(figsize=(14,9),facecolor='#f4f6f8'); ax=fig.add_subplot(111,projection='3d'); setup(ax,'Assembly study | PCB and keycaps shown for reference')
for i,(name,m) in enumerate(shells.items()):
    reflect = mirrored if i else lambda x:x.copy()
    shift=np.array([i*112,0,0])
    def show(part,c):
        part=reflect(part); part.apply_translation(shift); drawmesh(ax,part,c)
    sm=m.copy(); sm.apply_translation(shift); drawmesh(ax,sm,'#355772')
    pcbpoly=box(0,0,W,H)
    for x,y in holes: pcbpoly=pcbpoly.difference(Point(x,y).buffer(1.6))
    show(extrude(pcbpoly,1.6,8),'#257d68')
    for j,(x,y) in enumerate(keys):
        show(extrude(box(x-6.9,y-6.9,x+6.9,y+6.9),5,9.6),'#444b53')
        show(extrude(box(x-8.5,y-8.5,x+8.5,y+8.5),6,14.6),'#e4e8e9' if j<15 else '#e4aa58')
    cy=H-((119.79 if i else 117.25)-origin[1])
    show(extrude(box(54.5-origin[0]-18.3,cy-8.9,54.5-origin[0]+14.75,cy+8.9),1.6,15),'#313a46')
fig.text(.12,.08,'Reference components are schematic; only STL / 3MF parts are printable.\nOpen top preserves access to controller, power and reset. Optional switch plate is a separate part.',fontsize=12,color='#23374a')
rasterize(ax); fig.savefig(OUT/'preview_assembly.png',dpi=180); plt.close(fig)
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
