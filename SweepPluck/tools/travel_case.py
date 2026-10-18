"""Travel enclosure for bare SweepPluck PCB plus 3 mm nonslip pad; units: mm.
Run with the same geometry dependencies as case.py. Does not modify keyboard files.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import trimesh as tm
import sexpdata
from shapely.geometry import box
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'travel-case'

def rounded(w, h, r):
    return box(r, r, w-r, h-r).buffer(r, quad_segs=16)

def extrude(p, height, z=0):
    m = tm.creation.extrude_polygon(p, height, engine='earcut')
    m.apply_translation([0, 0, z])
    return m

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--half-depth', type=float, default=20,
                    help='inside depth per half; includes bottom padding')
    ap.add_argument('--mcu-gap', type=float, default=8.5,
                    help='design allowance from PCB top to lowest nice!nano module envelope; not a socket part dimension')
    args = ap.parse_args()
    depth = args.half_depth
    mcu_module_thickness = 3.2
    mcu_height = args.mcu_gap + mcu_module_thickness
    if args.mcu_gap < 0 or 3+1.6+mcu_height+1 > depth:
        raise ValueError('nice!nano stack exceeds cavity with 1 mm headroom; increase --half-depth')
    if depth < 15:
        raise ValueError('half-depth must be at least 15 mm')
    OUT.mkdir(exist_ok=True)
    board_path = ROOT/'SweepPluck.kicad_pcb'
    board = sexpdata.loads(board_path.read_text(encoding='utf-8'))
    def field(node, name):
        return next((v for v in node if isinstance(v,list) and v and str(v[0])==name),None)
    edges = [v for v in board if isinstance(v,list) and v and str(v[0])=='gr_line'
             and field(v,'layer')[1]=='Edge.Cuts']
    coords = np.array([field(e,k)[1:3] for e in edges for k in ('start','end')],float)
    pcb_xy = np.ptp(coords,axis=0)
    pcb_thickness = float(field(field(board,'general'),'thickness')[1])
    # Provisional unplugged connector envelope; confirm real module dimensions.
    cavity = pcb_xy + 8
    wall, floor = 2.4, 2.4
    w, h = cavity + 2*wall
    outer = rounded(w, h, 5)
    inner = rounded(*cavity, 2.6)
    from shapely.affinity import translate
    inner = translate(inner, wall, wall)
    shell = tm.boolean.union([extrude(outer, floor),
                              extrude(outer.difference(inner), depth+.1, floor-.1)], engine='manifold')
    # Lid registration lip: 0.30 mm radial clearance, 1.2 mm thickness.
    lip_outer = inner.buffer(-.30)
    lip_inner = inner.buffer(-1.50)
    root = extrude(inner.buffer(.8).difference(lip_inner), 1, floor+depth-1)
    lip = extrude(lip_outer.difference(lip_inner), 1.8, floor+depth-.2)
    lid = tm.boolean.union([shell, root, lip], engine='manifold')
    parts = {'base': shell, 'lid': lid}
    report = {'units':'mm', 'pcb_size':[*pcb_xy,pcb_thickness], 'nonslip_pad':3,
              'height_status':'K3 keycap proxy; nice!nano 3.2 mm envelope plus configurable socket mounting allowance; not physically verified',
              'controller':{'model':'nice!nano','mounting':'socketed, face down per keyboard README',
                            'module_thickness_mm':mcu_module_thickness,'module_reference':'https://nicekeyboards.com/docs/nice-nano/',
                            'pcb_to_module_lowest_envelope_gap_allowance_mm':args.mcu_gap,
                            'estimated_top_above_pcb_mm':mcu_height,
                            'headroom_inside_half_mm':depth-3-pcb_thickness-mcu_height,
                            'socket_part':'unspecified; gap is a design allowance, not measured hardware'},
              'keycap_reference':'https://www.keychron.com/products/low-profile-double-shot-pbt-keycap-set',
              'height_budget_mm':{'pad':3,'pcb':pcb_thickness,'switch_above_pcb_design_allowance_not_vendor_dimension':10,
                                  'keycap_proxy_height':4.4,'estimated_stack_without_deducting_stem_overlap':19,
                                  'clearance_each_half':depth-19,'max_mcu_height_above_pcb':depth-1-3-pcb_thickness},
              'cavity_xy':cavity.tolist(),
              'half_inside_depth':depth, 'closed_size':[w,h,2*(floor+depth)],
              'extra_bottom_padding':0, 'maximum_assembly_height_including_pad_with_2mm_face_gap':depth-1,
              'lip_clearance_each_side':.3, 'parts':{},
              'source_sha256':{'SweepPluck.kicad_pcb':hashlib.sha256(board_path.read_bytes()).hexdigest()}}
    for name,m in parts.items():
        assert m.is_watertight and m.is_winding_consistent and m.volume>0
        assert len(m.split()) == 1
        m.export(OUT/f'{name}.stl')
        report['parts'][name] = {'size':m.extents.tolist(), 'watertight':True,
                                'components':1, 'volume_mm3':float(m.volume)}
    closed_lid = lid.copy()
    transform = np.eye(4)
    transform[1,1] = -1
    transform[2,2] = -1
    transform[1,3] = h
    transform[2,3] = 2*(floor+depth)
    closed_lid.apply_transform(transform)
    collision = tm.boolean.intersection([shell,closed_lid], engine='manifold')
    collision_volume = float(collision.volume) if len(collision.faces) else 0.
    assert abs(collision_volume) < .001
    report['closed_shell_intersection_mm3'] = collision_volume
    # PCB passage through the lid registration lip.
    report['lip_opening_xy'] = (cavity-3).tolist()
    assert np.all(cavity-3 > pcb_xy)
    # Cut two removable 4 mm EVA rings. Their pocket locates the bare PCB and pad.
    # Drawing coordinates share the cavity outline; no keyboard housing required.
    cw,ch = cavity
    pw,ph = pcb_xy+.8
    foam_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{cw}mm" height="{ch}mm" viewBox="0 0 {cw} {ch}">
<title>Cut two 4 mm EVA locator rings; 1:1 mm; verify printed scale</title>
<rect x="0.2" y="0.2" width="{cw-.4}" height="{ch-.4}" rx="2.4" fill="none" stroke="black" stroke-width="0.15"/>
<rect x="{(cw-pw)/2}" y="{(ch-ph)/2}" width="{pw}" height="{ph}" fill="none" stroke="black" stroke-width="0.15"/>
</svg>'''
    (OUT/'foam_locator_1to1.svg').write_text(foam_svg,encoding='utf-8')
    report['foam_locator'] = {'thickness':4, 'pocket_xy':[pw,ph], 'quantity':2,
                              'note':'hand-fit soft foam; relieve around underside solder joints and connectors'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    fig=plt.figure(figsize=(12,6),facecolor='#f4f6f8')
    for idx,(name,m) in enumerate(parts.items(),1):
        ax=fig.add_subplot(1,2,idx,projection='3d')
        ax.plot_trisurf(m.vertices[:,0],m.vertices[:,1],m.vertices[:,2],triangles=m.faces,
                        color='#5a8291',linewidth=0,shade=True)
        ax.set(xlim=(0,w),ylim=(0,h),zlim=(0,floor+depth+2),title=name.upper())
        ax.set_box_aspect((w,h,floor+depth+2)); ax.view_init(48,-65); ax.set_axis_off()
    fig.suptitle(f'SweepPluck travel case | closed {w:.2f} x {h:.2f} x {2*(floor+depth):.1f} mm')
    fig.text(.08,.05,'3 mm pad + 1.6 mm PCB + 10 mm switch allowance + 4.4 mm K3 keycap proxy.\n1 mm headroom per half at default depth. MCU height must fit this envelope.',fontsize=11)
    fig.savefig(OUT/'preview.png',dpi=160); plt.close(fig)
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    main()
