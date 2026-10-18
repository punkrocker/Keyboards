from pathlib import Path
import pcbnew as p
import xml.etree.ElementTree as E
import json, collections
D=Path(__file__).resolve().parents[1]
results={}
for name in ['SweepPluck','SweepPluck-right']:
    b=p.LoadBoard(str(D/(name+'.kicad_pcb')))
    tree=E.parse(D/'verification'/(name+'.xml'))
    sch={(n.get('ref'),n.get('pin')):net.get('name').lstrip('/') for net in tree.findall('.//nets/net') for n in net.findall('node') if not net.get('name').startswith('unconnected-')}
    pcb={(f.GetReference(),z.GetNumber()):z.GetNetname() for f in b.GetFootprints() for z in f.Pads() if z.GetNumber() and z.GetNetname()}
    assert pcb==sch,(name,pcb.items()-sch.items(),sch.items()-pcb.items())
    keys=[f for f in b.GetFootprints() if 'keyswitch_' in str(f.GetFPID().GetLibItemName())]
    assert len(keys)==17
    assert all(abs(f.GetOrientationDegrees())<.001 for f in keys)
    report=json.loads((D/'verification'/('drc-'+name+'.json')).read_text(encoding='utf-8'))
    counts=collections.Counter((v['type'],v['severity']) for v in report['violations'])
    print(name,len(pcb),'matching net/pin assignments',counts)
    for v in report['violations'][:4]: print(v['description'])
    results[name]={'keys':len(keys),'net_pin_assignments':len(pcb),'schematic_matches_pcb':True,'unconnected_items':len(report['unconnected_items']),'drc':{f'{a}/{c}':n for (a,c),n in counts.items()}}
(D/'verification'/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

