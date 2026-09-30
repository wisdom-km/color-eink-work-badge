"""Independent export/readback, mesh topology and insertion-path checks."""
from pathlib import Path
import collections,json,struct
import cadquery as cq
import build_enclosure as M
from cad_helpers import inspect,overlap_volume
parts={'front_frame':M.frame(),'back_cover':M.cover()}
results={}
for name,shape in parts.items():
    step=cq.importers.importStep(str(M.OUT/f'portrait_{name}.step')).val()
    original=inspect(shape); imported=inspect(step)
    dv=abs(shape.Volume()-step.Volume())
    assert imported['valid'] and imported['solids']==1 and dv<1e-5
    data=(M.OUT/f'portrait_{name}.stl').read_bytes();n=struct.unpack_from('<I',data,80)[0]
    assert len(data)==84+50*n, 'expected binary STL'
    edges=collections.Counter();directed=collections.Counter();degenerate=0
    for i in range(n):
        nums=struct.unpack_from('<12fH',data,84+50*i)
        verts=[tuple(round(v,5) for v in nums[3+3*j:6+3*j]) for j in range(3)]
        if len(set(verts))<3:degenerate+=1
        for j in range(3):
            a,b=verts[j],verts[(j+1)%3];edges[tuple(sorted((a,b)))]+=1;directed[(a,b)]+=1
    bad=[count for count in edges.values() if count!=2]
    orientation_bad=sum(1 for a,b in directed if directed[(a,b)]!=directed[(b,a)])
    assert not bad and not degenerate and not orientation_bad,(name,len(bad),degenerate,orientation_bad)
    results[name]={'step_readback':imported,'step_volume_delta_mm3':dv,'stl_triangles':n,
                  'stl_unpaired_edges':len(bad),'stl_degenerate_triangles':degenerate,
                  'stl_inconsistent_directed_edges':orientation_bad}
sweep={'status':'NOT_APPLICABLE_EXTERNAL_CARD_CARRIER_CANCELLED'}
report={'status':'PASS_EXPORT_TOPOLOGY_ONLY','parts':results,'card_insertion_sweep_interference_mm3':sweep,
        'limitations':['STL topology is not print-process qualification','Nominal clearances do not replace physical tolerance/warpage checks','No finished populated PCB in these assemblies']}
(M.REPORT/'export_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
