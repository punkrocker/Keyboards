"""Annotate the actual KiCad SVG exports; coordinates come from the pin CSV."""
from pathlib import Path
import csv
import copy
import xml.etree.ElementTree as ET

D = Path(__file__).resolve().parents[1]
OUT = D / 'power-guide'
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
rows = list(csv.DictReader((D/'SweepPluck-pins.csv').open(encoding='utf-8-sig')))
def tag(parent, name, **attrs):
    return ET.SubElement(parent, '{'+NS+'}'+name, {k.replace('_','-'):str(v) for k,v in attrs.items()})

for back in (False, True):
    side = 'RIGHT' if back else 'LEFT'
    source = ET.parse(D/('SweepPluck-back.svg' if back else 'SweepPluck-preview.svg')).getroot()
    root = ET.Element('{'+NS+'}svg', {'width':'1800','height':'1400','viewBox':'0 0 1800 1400'})
    tag(root,'rect',width=1800,height=1400,fill='white')
    def text(x,y,s,size=28,color='#172b45'):
        t=tag(root,'text',x=x,y=y,font_family='Microsoft YaHei',font_size=size,fill=color)
        t.text=s
    text(50,60,'SweepPluck · 实际 PCB 电池 / 开关焊接标记',40)
    text(50,110,('右手 B 面（已镜像）' if back else '左手 F 面')+' · 从键轴安装面看，板顶朝上')
    def xy(r):
        x=float(r['x_mm'])-35.475
        return (95.25-x if back else x,float(r['y_mm'])-50.475)
    def add_board(x,y,w,h,viewbox,detail=False):
        board=copy.deepcopy(source)
        board.attrib.update(x=str(x),y=str(y),width=str(w),height=str(h),viewBox=' '.join(map(str,viewbox)))
        board.set('preserveAspectRatio','none')
        root.append(board)
        def pos(r):
            px,py=xy(r)
            return x+(px-viewbox[0])/viewbox[2]*w,y+(py-viewbox[1])/viewbox[3]*h
        for ref,label,c in [('BATP1','+','#cf2929'),('BATG1','−','#194f9c')]:
            r=next(r for r in rows if r['reference']==ref)
            px,py=pos(r)
            tag(root,'circle',cx=px,cy=py,r=20 if not detail else 26,fill='none',stroke=c,stroke_width=5)
            text(px-52,py+10,label,34,c)
        pads=[r for r in rows if r['reference']=='SW_POWER1' and r['copper_layers']==('B.Cu' if back else 'F.Cu')]
        if detail:
            for r in pads:
                px,py=pos(r)
                tag(root,'circle',cx=px,cy=py,r=17,fill='none',stroke='#07826e',stroke_width=4)
                tag(root,'line',x1=px,y1=py-20,x2=px,y2=py-65,stroke='#07826e',stroke_width=3)
                text(px-14,py-78,r['pad'],28,'#07826e')
        else:
            pts=[pos(r) for r in pads]
            px=sum(p[0] for p in pts)/3; py=pts[0][1]
            tag(root,'rect',x=px-38,y=py-24,width=76,height=50,fill='none',stroke='#07826e',stroke_width=4)
            text(px-30,py-38,'PWR',23,'#07826e')
    add_board(50,160,1100,924,[0,0,95.25,79.9846])
    text(1210,215,'红圈 +：电池正极',29,'#cf2929')
    text(1210,260,'BATP1 / BAT',26,'#cf2929')
    text(1210,325,'蓝圈 −：电池负极',29,'#194f9c')
    text(1210,370,'BATG1 / GND',26,'#194f9c')
    text(1210,435,'绿框：SW_POWER1 电源开关',26,'#07826e')
    text(1210,495,'下方为同一 PCB 区域放大：',26)
    # Crop of actual exported copper, pads and silk, with identical coordinates.
    bx=95.25-(84-35.475) if back else 69-35.475
    add_board(1220,545,510,680,[bx,56,15,20],True)
    text(50,1155,'开关：1 脚悬空；2 脚 BAT；3 脚 RAW。焊接三个脚及外壳固定焊盘，不要连锡。',28)
    text(50,1210,'ON：2–3 脚导通；OFF：2–3 脚断开。每块 PCB 只在键轴所在面安装一只开关。',28)
    text(50,1265,'电源路径：电池 + → BAT → 开关 → RAW；电池 − → GND。',28)
    text(50,1320,'操作前断开电池和 USB。RAW 对应的主控电池输入、电压及充电能力须按实际模块核对。',25)
    ET.ElementTree(root).write(OUT/f'power_board_{side}.svg',encoding='utf-8',xml_declaration=True)
