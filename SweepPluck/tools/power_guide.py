"""Draw power soldering details using coordinates from the released pin CSV."""
from pathlib import Path
import csv
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'power-guide'
OUT.mkdir(exist_ok=True)
rows = list(csv.DictReader((ROOT / 'SweepPluck-pins.csv').open(encoding='utf-8-sig')))
font_path = Path('C:/Windows/Fonts/msyh.ttc')
def font(n):
    return ImageFont.truetype(str(font_path), n)

for side, layer, mirror in [('LEFT', 'F.Cu', False), ('RIGHT', 'B.Cu', True)]:
    im = Image.new('RGB', (1500, 1200), '#f5f7fa')
    d = ImageDraw.Draw(im)
    def text(x, y, s, n=26, color='#172b45'):
        d.text((x, y), s, font=font(n), fill=color)
    text(55, 30, f'SweepPluck · 电池与电源开关 · {side}', 38)
    text(55, 88, '从键轴安装面看：' + ('右手 B 面（已镜像）' if mirror else '左手 F 面'))
    text(55, 130, '方向与 PCB 预览一致：主键区在上，主控 / 拇指键区在下。局部图按实际坐标绘制。', 24)
    d.rounded_rectangle((40, 190, 1460, 835), radius=20, fill='white', outline='#ccd5e0', width=2)
    def xy(x, y):
        return (int(740 + (-1 if mirror else 1) * (x-76)*30), int(290+(y-110)*30))
    # Switch body, non-electrical anchor pads and unplated locating holes.
    a,b=xy(75.2,110.65),xy(81.8,113.5)
    d.rectangle((min(a[0],b[0]),a[1],max(a[0],b[0]),b[1]), outline='#8494a8', width=3)
    for x in (74.8,82.2):
        for y in (110.9,113.1):
            px,py=xy(x,y)
            d.rectangle((px-13,py-13,px+13,py+13),fill='#b8c2ce')
    for x in (77,80):
        px,py=xy(x,112)
        d.ellipse((px-12,py-12,px+12,py+12),outline='#8494a8',width=3)
    colors={'BAT':'#d13d3d','RAW':'#d58a10','GND':'#24364b'}
    selected=[r for r in rows if r['reference'] in ('BATP1','BATG1') or (r['reference']=='SW_POWER1' and r['copper_layers']==layer)]
    assert len(selected)==5
    for r in selected:
        x,y=xy(float(r['x_mm']),float(r['y_mm']))
        net=r['net']; c=colors.get(net,'#6b7f94')
        if r['reference']=='SW_POWER1':
            expected={'1':'unconnected-(SW_POWER1-Pad1)','2':'BAT','3':'RAW'}[r['pad']]
            assert net==expected
            d.rectangle((x-13,y-19,x+13,y+19),fill=c)
            # Vertical callouts preserve the real horizontal pad ordering.
            text(x-24,205,r['pad']+'脚',21,c)
            text(x-25,240,{'1':'NC','2':'BAT','3':'RAW'}[r['pad']],18,c)
        else:
            d.ellipse((x-22,y-22,x+22,y+22),fill=c)
            d.ellipse((x-7,y-7,x+7,y+7),fill='white')
            label='BATP1 / BAT · 电池正极 +' if net=='BAT' else 'BATG1 / GND · 电池负极 −'
            if mirror:
                d.line((x+25,y,x+80,y),fill=c,width=4)
                text(x+90,y-19,label,24,c)
            else:
                d.line((x-25,y,x-80,y),fill=c,width=4)
                text(75,y-19,label,24,c)
    text(75,760,'灰色小方块：开关外壳固定焊盘；空心小圆：定位孔（不焊）。',24)
    text(55,865,'电源连接',30)
    text(55,920,'电池 + → BATP1 / BAT → 开关 2 脚 — 3 脚 → RAW → 主控',27,'#b0362e')
    text(55,970,'电池 − → BATG1 / GND → 主控 GND',27)
    text(55,1030,'ON：2–3 导通；OFF：2–3 断开。1 脚照常焊到对应焊盘，但网络悬空。',25)
    text(55,1080,'只在键轴所在面装一只开关。不要把相邻信号脚或两面的焊盘用锡桥短接。',25)
    text(55,1130,'焊接 / 通断测量前断开电池与 USB；RAW 是 PCB 网络名，主控供电兼容性须另核对。',23)
    im.save(OUT / f'power_{side}.png')


