"""Read-only PCB preview from actual KiCad layers and Edge.Cuts.
Uses system KiCad CLI and PySide2 renderer, no fictional component positions.
Run with /usr/bin/python3; does not open or control the user's GUI.
"""
from pathlib import Path
import os,re,subprocess,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parents[2];PCB=ROOT/'hardware/portrait/pcb/badge.kicad_pcb';OUT=H/'output'
env=dict(os.environ,HOME='/tmp/pcb-render-home',XDG_CONFIG_HOME='/tmp/pcb-render-conf',XDG_CACHE_HOME='/tmp/pcb-render-cache',XDG_DATA_HOME='/tmp/pcb-render-data',QT_QPA_PLATFORM='offscreen')
for name,layers in [('pcb_back_layout','B.Cu,B.SilkS,Edge.Cuts'),('pcb_edge_crop','Edge.Cuts')]:
 subprocess.run(['kicad-cli','pcb','export','svg','--layers',layers,'--mirror','--page-size-mode','2','--exclude-drawing-sheet','--mode-single','-o',str(OUT/(name+'.svg')),str(PCB)],env=env,check=True,stdout=subprocess.DEVNULL)
s=(OUT/'pcb_edge_crop.svg').read_text()
points=[(float(a),float(b)) for a,b in re.findall(r'[ML]\s*([-\d.]+)\s*[, ]\s*([-\d.]+)',s)]
x0=min(p[0] for p in points);y0=min(p[1] for p in points);x1=max(p[0] for p in points);y1=max(p[1] for p in points)
assert abs((x1-x0)-58)<.001 and abs((y1-y0)-92.64)<.001, (x0,y0,x1,y1)
s=(OUT/'pcb_back_layout.svg').read_text();s=re.sub(r'width="[^"]+" height="[^"]+" viewBox="[^"]+"',f'width="58mm" height="92.64mm" viewBox="{x0} {y0} 58 92.64"',s,count=1)
path=OUT/'pcb_back_layout_clipped.svg';path.write_text(s)
os.environ.update({k:env[k] for k in ('HOME','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME','QT_QPA_PLATFORM')})
from PySide2 import QtCore,QtGui,QtSvg
app=QtGui.QGuiApplication([]);r=QtSvg.QSvgRenderer(str(path));w=640;hh=round(w*92.64/58)
im=QtGui.QImage(w,hh,QtGui.QImage.Format_ARGB32);im.fill(QtGui.QColor('#24372d'));p=QtGui.QPainter(im);r.render(p);p.end();assert im.save(str(OUT/'pcb_back_layout_clipped.png'))
(H/'validation/layout_preview_source.json').write_text(json.dumps({'board_sha256':hashlib.sha256(PCB.read_bytes()).hexdigest(),'method':'KiCad B.Cu/B.SilkS/Edge.Cuts mirrored, clipped to exact board Edge.Cuts bbox','rect_mm':[x0,y0,x1,y1],'not_a_photo':True},indent=2)+'\n')
