"""Mark the selected U1 assembly holes on the actual KiCad board exports."""
from pathlib import Path
import csv
import copy
import xml.etree.ElementTree as ET

D=Path(__file__).resolve().parents[1]
OUT=D/'mcu-guide'; OUT.mkdir(exist_ok=True)
NS='http://www.w3.org/2000/svg'; ET.register_namespace('',NS)
rows=list(csv.DictReader((D/'SweepPluck-pins.csv').open(encoding='utf-8-sig')))
pins=[r for r in rows if r['reference']=='U1']
def tag(parent,name,**attrs):
    return ET.SubElement(parent,'{'+NS+'}'+name,{k.replace('_','-'):str(v) for k,v in attrs.items()})
for back in (False,True):
    side='RIGHT' if back else 'LEFT'; letter='R' if back else 'L'
    source=ET.parse(D/('SweepPluck-back.svg' if back else 'SweepPluck-preview.svg')).getroot()
    root=ET.Element('{'+NS+'}svg',{'width':'1800','height':'2200','viewBox':'0 0 1800 2200'})
    tag(root,'rect',width=1800,height=2200,fill='white')
    def text(x,y,s,size=28,color='#17354b'):
        t=tag(root,'text',x=x,y=y,font_family='Microsoft YaHei',font_size=size,fill=color); t.text=s
    text(50,60,'SweepPluck · 主控 U1 焊接位置',42)
    text(50,115,('右手 B 面（已镜像）' if back else '左手 F 面')+' · 从键轴安装面看，板顶朝上',30)
    selected=[r for r in pins if r['assembly']==side]
    assert len(selected)==24 and len({r['pad'] for r in selected})==24
    def xy(r):
        x=float(r['x_mm'])-35.475
        return (95.25-x if back else x,float(r['y_mm'])-50.475)
    def board(x,y,w,h,vb,detail=False):
        layer=copy.deepcopy(source)
        layer.attrib.update(x=str(x),y=str(y),width=str(w),height=str(h),viewBox=' '.join(map(str,vb)),preserveAspectRatio='none')
        root.append(layer)
        def pos(r):
            px,py=xy(r); return x+(px-vb[0])/vb[2]*w,y+(py-vb[1])/vb[3]*h
        for r in selected:
            px,py=pos(r)
            tag(root,'circle',cx=px,cy=py,r=18 if detail else 9,fill='none',stroke='#008b60',stroke_width=5 if detail else 3)
        if detail:
            for ry in sorted({float(r['y_mm']) for r in pins}):
                r=next(r for r in pins if float(r['y_mm'])==ry)
                _,py=pos(r); active=r['assembly']==side
                text(1550,py+9,letter+'：焊这排' if active else '另一组：留空',25,'#008b60' if active else '#637082')
            pts=[pos(r) for r in selected]; center_y=(min(p[1] for p in pts)+max(p[1] for p in pts))/2
            text(x+330,center_y-15,'主控放在绿色两排孔之间',30,'#008b60')
            text(x+330,center_y+35,'FACE DOWN：元件面 / USB 面朝 PCB',27)
            # USB is at the pin-1 / pin-24 end of the selected module.
            a=next(r for r in selected if r['pad']=='1'); b=next(r for r in selected if r['pad']=='24')
            ax,ay=pos(a); bx,by=pos(b); cy=(ay+by)/2
            sign=1 if back else -1; end=ax+sign*125
            tag(root,'line',x1=ax,y1=cy,x2=end,y2=cy,stroke='#d16a00',stroke_width=8)
            tag(root,'path',d=f'M {end-sign*20} {cy-15} L {end} {cy} L {end-sign*20} {cy+15}',fill='none',stroke='#d16a00',stroke_width=7)
            text(ax-110 if not back else ax-80,cy+85,'USB 朝板外缘',26,'#d16a00')
            for r,label in [(a,'TX / 1 脚端'),(b,'RAW / 24 脚端')]:
                px,py=pos(r)
                text(px+30 if not back else px-220,py-30 if r is a else py+50,label,23,'#d16a00')
    board(50,160,1050,882,[0,0,95.25,79.9846])
    for y,s in [(220,'绿色圆圈 = 本侧主控焊孔'),(285,'共两排，每排 12 孔。'),(380,'右手：只选 R 组。' if back else '左手：只选 L 组。'),(445,'其余两排孔留空。'),(540,'USB 朝右侧外缘 →' if back else '← USB 朝左侧外缘'),(635,'主控元件面朝向键盘 PCB。'),(700,'用排针 / 插座留出元件高度。'),(765,'每块 PCB 只装一个主控。')]:
        text(1150,y,s,29)
    text(50,1120,'U1 区域放大：焊绿色圈出的 24 个孔；另一组不焊、不短接。',32)
    crop_x=95.25-(74-35.475) if back else 34-35.475
    board(80,1200,1440,864,[crop_x,106-50.475,40,24],True)
    text(50,2140,'安装前按主控引脚标记核对 TX / RAW 端；断开电池与 USB，避免插反或贴板焊接。',28)
    ET.ElementTree(root).write(OUT/f'mcu_board_{side}.svg',encoding='utf-8',xml_declaration=True)
