"""MX hole identification from the actual reversible KiCad footprints."""
from pathlib import Path
import json, math, argparse
import sexpdata as sx
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
from matplotlib import font_manager

D=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('family',nargs='?',default='MX',choices=['MX','Choc_V1','Choc_V2','Alps'])
family=parser.parse_args().family
label=family.replace('_',' ')
OUT=D/('mx-guide' if family=='MX' else 'switch-guides'); OUT.mkdir(exist_ok=True)
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False
def get(n,k): return next((i for i in n if isinstance(i,list) and i and str(i[0])==k),None)
b=sx.loads((D/'SweepPluck.kicad_pcb').read_text(encoding='utf-8'))
fps={get(f,'property')[2]:f for f in b if isinstance(f,list) and f and str(f[0])=='footprint'}
def pads(f): return [p for p in f if isinstance(p,list) and p and str(p[0])=='pad']
RED='#ed6246'; BLUE='#328bc4'; GOLD='#f6bf49'; GRAY='#81918e'
selected={'MX':[(-3.8,-2.55),(2.54,-5.08)],'Alps':[(-2.5,-4),(5,-5.55)],
          'Choc_V1':[(-5.1,3.9),(0,5.9)],'Choc_V2':[(-5.1,3.9),(0,5.9)]}[family]
locators=() if family=='Alps' else ((-5.08,5.08) if family=='MX' else (-5.5,5.5))
legend={'MX':'红色 ①②：两个金属脚，需要焊接\n蓝色：中心定位柱，Ø4.9 mm 孔，不焊\n黄色：五脚 MX 的两个塑料柱，不焊\n三脚 MX：两处黄色孔留空',
        'Alps':'红色 ①②：两个金属脚，需要焊接\n中心大孔及左右定位槽：留空\n① 与 MX 共用竖长孔，使用中下段\nAlps 需另配匹配轴体的定位板',
        'Choc_V1':'红色 ①②：两个金属脚，需要焊接\n蓝色：中心定位柱，不焊\n黄色：两侧塑料定位柱，不焊\n使用下方焊孔，上方 MX/Alps 孔留空',
        'Choc_V2':'红色 ①②：两个金属脚，需要焊接\n蓝色：中心定位柱，不焊\n黄色：两侧塑料定位柱，不焊\n金属脚孔位与 Choc V1 相同'}[family]
def contains(p,xy):
    x,y=get(p,'at')[1:3]; drill=get(p,'drill'); dims=[v for v in drill[1:] if isinstance(v,(int,float))]
    w,h=(dims*2)[:2] if len(dims)==1 else dims[:2]
    return abs(xy[0]-x)<=w/2 and abs(xy[1]-y)<=h/2
checks=[]
for i in range(1,18):
    f=fps['SW'+str(i)]
    for back in (False,True):
        xy=[(-x if back else x,y) for x,y in selected]
        found=[next(p for p in pads(f) if str(p[2])=='thru_hole' and contains(p,q)) for q in xy]
        nets=[get(p,'net')[-1] for p in found]
        assert set(nets)=={'GND','Switch'+str(i)}
        checks.append({'switch':i,'assembly_side':'B' if back else 'F','local_pins_kicad_mm':xy,'nets':nets})

def shape(ax,x,y,w,h,color,edge=None,lw=.5,z=2):
    ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle=f'round,pad=0,rounding_size={min(w,h)/2}',facecolor=color,edgecolor=edge or color,linewidth=lw,zorder=z))
def localpads(ax,f,back,detail=False):
    for p in pads(f):
        x,y=get(p,'at')[1:3]; x=-x if back else x
        w,h=get(p,'size')[1:3]
        drill=get(p,'drill'); ds=[v for v in drill[1:] if isinstance(v,(int,float))]
        dw,dh=(ds[0],ds[0]) if len(ds)==1 else ds[:2]
        npth=str(p[2])=='np_thru_hole'
        shape(ax,x,y,w,h,'#e2b96b' if not npth else '#b6c4bc',z=2)
        shape(ax,x,y,dw,dh,'#edf1f2',z=3)
    # Every view uses a viewer-facing coordinate system, with board top above.
    for j,(x,y) in enumerate(selected):
        ax.add_patch(Circle((x,y),1.17,fill=False,edgecolor=RED,linewidth=2.6,zorder=5))
        ax.text(x+1.35,y+.3,str(j+1),color=RED,fontsize=12 if detail else 7,weight='bold',zorder=8)
    if family!='Alps': ax.add_patch(Circle((0,0),2.55,fill=False,edgecolor=BLUE,linewidth=2,zorder=4))
    for x in locators:
        ax.add_patch(Circle((x,0),1.2,fill=False,edgecolor=GOLD,linewidth=2,zorder=4))
    ax.set(xlim=(-9.5,9.5),ylim=(9.5,-9.5),aspect='equal')

for back in (False,True):
    fig=plt.figure(figsize=(16,10),facecolor='#f4f6f7')
    side='B 面 / RIGHT 右手装轴' if back else 'F 面 / LEFT 左手装轴'
    fig.suptitle('SweepPluck v3.1 · '+label+' 轴孔位 — '+side,fontsize=21,y=.97)
    fig.text(.06,.905,'视角：从该侧正对 PCB；板顶朝上。红圈 ①② 是此面装 '+label+' 轴时使用的两个金属焊脚孔。',fontsize=12,color='#273d48')
    board=fig.add_axes([.045,.20,.56,.65]); board.set_facecolor('#dfe9e3')
    board.add_patch(Rectangle((0,0),95.25,80,facecolor='#315c53',edgecolor='#183d36',lw=2))
    for ref,f in fps.items():
        at=get(f,'at'); ox,oy=at[1]-35.475,at[2]-50.475
        if back: ox=95.25-ox
        angle=math.radians(at[3] if len(at)>3 else 0)
        for p in pads(f):
            px,py=get(p,'at')[1:3]
            dx=px*math.cos(angle)+py*math.sin(angle); dy=-px*math.sin(angle)+py*math.cos(angle)
            x,y=ox+(-dx if back else dx),oy+dy
            w,h=get(p,'size')[1:3]
            dr=get(p,'drill')
            if abs(math.sin(angle))>.5: w,h=h,w
            shape(board,x,y,w,h,'#c1aa70' if str(p[2])!='np_thru_hole' else '#eff3f1',z=2)
            if dr:
                dims=[v for v in dr[1:] if isinstance(v,(int,float))]; dw,dh=(dims[0],dims[0]) if len(dims)==1 else dims[:2]
                shape(board,x,y,dw,dh,'#edf1f2',z=3)
        if ref.startswith('SW') and ref[2:].isdigit():
            board.add_patch(Rectangle((ox-7,oy-7),14,14,fill=False,edgecolor='#6e9287',lw=.6,zorder=1))
            for j,(dx,dy) in enumerate(selected):
                board.add_patch(Circle((ox+dx,oy+dy),1.15,fill=False,edgecolor=RED,lw=1.6,zorder=5))
            if family!='Alps': board.add_patch(Circle((ox,oy),2.53,fill=False,edgecolor=BLUE,lw=1,zorder=4))
            for dx in locators: board.add_patch(Circle((ox+dx,oy),1.18,fill=False,edgecolor=GOLD,lw=1,zorder=4))
            board.text(ox,oy+8.3,ref,ha='center',fontsize=6.5,color='white',zorder=6)
    board.set(xlim=(-3,98.25),ylim=(83,-3),aspect='equal'); board.axis('off')
    detail=fig.add_axes([.66,.39,.30,.43]); detail.set_facecolor('#315c53'); localpads(detail,fps['SW1'],back,True)
    detail.set_title('单键放大（17 个键使用同一规则）',fontsize=13,pad=12)
    detail.set_xticks([]); detail.set_yticks([])
    if family=='MX':
        annotations=[('① 圆孔：左上',selected[0],(-8.5,-8)),('② 竖长孔：右上\n使用长孔上段',selected[1],(1,-8))]
    elif family=='Alps':
        annotations=[('① 竖长孔：左上\n使用长孔中下段',selected[0],(-8.5,-8)),('② 横长孔：右上',selected[1],(1,-8))]
    else:
        annotations=[('① 左下横长孔',selected[0],(-8.8,7.9)),('② 正下横长孔',selected[1],(.6,8.4))]
    for text,xy,txt in annotations:
        detail.annotate(text,xy=xy,xytext=txt,color=RED,fontsize=10.5,arrowprops={'arrowstyle':'->','color':RED},zorder=9)
    if family!='Alps': detail.annotate('中心塑料柱',xy=(0,0),xytext=(-3,-8 if family.startswith('Choc') else 7.4),color='#b7e2ff',fontsize=11,arrowprops={'arrowstyle':'->','color':BLUE},zorder=9)
    fig.text(.655,.265,legend,fontsize=12,linespacing=1.7,color='#233c49')
    note={'MX':'② 位于与 Alps 共用的连续镀铜长孔内。','Alps':'① 位于与 MX 共用的连续镀铜长孔内。','Choc_V1':'与 Choc V2 使用相同的一对金属脚孔。','Choc_V2':'与 Choc V1 使用相同的一对金属脚孔。'}[family]
    a,c=selected
    fig.text(.06,.125,f'孔位以轴心为原点（当前观看方向：右为 +X，下为 +Y）\n① ({a[0]:+.2f}, {a[1]:+.2f}) mm；② ({c[0]:+.2f}, {c[1]:+.2f}) mm。'+note,fontsize=12,color='#233c49',linespacing=1.7)
    fig.text(.06,.045,'注意：F 面和 B 面图分别表示左手、右手的装轴方案，选用不同的一对实体焊孔。\n同一颗已插入的轴翻到背面焊接时，仍焊其实际穿出的两脚；不要再照另一装轴图换孔。',fontsize=11,color='#8b432e',linespacing=1.6)
    name=family+('_back_RIGHT' if back else '_front_LEFT')
    fig.savefig(OUT/(name+'.png'),dpi=180); fig.savefig(OUT/(name+'.svg')); plt.close(fig)
(OUT/('pin_checks.json' if family=='MX' else family+'_pin_checks.json')).write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
print('Verified 34 '+family+' terminal pairs against actual PCB nets. Generated F/LEFT and mirrored B/RIGHT PNG + SVG.')
