"""Dimension-driven smoke-shell review, with actual firmware/PCB preview inputs.
This is an exterior direction drawing, not an optical simulation or a photo.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import build_enclosure as M
P=M.P;E=M.E;OUT=M.OUT;S=7
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc';BOLD='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
def f(n,b=False):return ImageFont.truetype(BOLD if b else FONT,n)
preview=M.ROOT/'tools/portrait_display/output/preview400x600/portrait.png'
if not preview.exists(): preview=M.HERE/'assets/firmware_demo_400x600.png'
if preview.exists():screen=Image.open(preview).convert('RGB').resize((400,600),Image.Resampling.NEAREST)
else:
 screen=Image.new('RGB',(400,600),'#f4f2ed');ImageDraw.Draw(screen).text((30,200),'400 x 600\nDEMO ONLY',font=f(28,True),fill='#202c36')
screen.save(OUT/'portrait_screen_demo_400x600.png')
im=Image.new('RGB',(1700,1280),'#eef2f5');d=ImageDraw.Draw(im)
d.text((78,51),'CHROMA  /  P1.1 REV B C1',font=f(25,True),fill='#61717f')
d.text((76,92),'一体式 · 烟灰半透竖版工牌',font=f(44,True),fill='#132b3a')
d.text((78,157),'3.6 英寸六色墨水屏  ·  集成挂绳槽  ·  齐平可维护后盖',font=f(22),fill='#647886')
W,H=E['outer_w']*S,E['outer_h']*S;by=282;xs=[150,1010]
for side,bx in enumerate(xs):
 d.rounded_rectangle((bx+10,by+13,bx+W+10,by+H+13),radius=M.CORNER_R*S,fill='#cad2d8')
 d.rounded_rectangle((bx,by,bx+W,by+H),radius=M.CORNER_R*S,fill='#737c84',outline='#aeb6bc',width=3)
 d.rounded_rectangle((bx+5,by+5,bx+W-5,by+H-5),radius=(M.CORNER_R-.5)*S,outline='#bcc4c9',width=2)
 # Continuous seam is on rear perimeter; no external carrier.
 d.rounded_rectangle((bx+12,by+12,bx+W-12,by+H-12),radius=(M.CORNER_R-.9)*S,outline='#515b64',width=2)
 def xy(x,y):return bx+(x-M.OX0)*S,by+(y-M.TOP)*S
 if side==0:
  x0,y0,x1,y1=P['window_rect'];a=xy(x0-.3,y0-.3);b=xy(x1+.3,y1+.3)
  d.rectangle((*a,*b),fill='#303d48')
  a=xy(P['active_x'],P['active_y']);im.paste(screen.resize((round(P['active_w']*S),round(P['active_h']*S))),tuple(round(v) for v in a))
  d.text((bx+W/2,by+H-72),'CHROMA / OPEN HARDWARE',font=f(15),fill='#d8dfe4',anchor='mt')
 else:
  # True B.Cu+silkscreen plot of the candidate PCB, clipped to Edge.Cuts.
  p=OUT/'pcb_back_layout_clipped.png'
  if p.exists():
   board=Image.open(p).convert('RGB')
   board=board.resize((round(M.BW*S),round(M.BH*S)))
   board=Image.blend(board,Image.new('RGB',board.size,'#53616b'),.48)
   im.paste(board,tuple(round(v) for v in xy(0,0)))
  else:
   a=xy(0,0);b=xy(M.BW,M.BH);d.rounded_rectangle((*a,*b),radius=2*S,fill='#334b47')
  r=M.C['battery']['rect'];a=xy(M.BW-r[2],r[1]);b=xy(M.BW-r[0],r[3]);
  d.rounded_rectangle((*a,*b),radius=2*S,fill='#8c979f',outline='#c6cdd0',width=2)
  d.text(((a[0]+b[0])/2,(a[1]+b[1])/2-25),'LiPo',font=f(23,True),fill='#e7edf0',anchor='mt')
  d.text(((a[0]+b[0])/2,(a[1]+b[1])/2+13),'500mAh 保护电池',font=f(16),fill='#dee5e9',anchor='mt')
  for x,y in M.SCREWS:
   q=xy(M.BW-x,y);d.ellipse((q[0]-9,q[1]-9,q[0]+9,q[1]+9),fill='#a9b2b9',outline='#e2e6ea',width=2);d.line((q[0]-4,q[1],q[0]+4,q[1]),fill='#52606b',width=2)
  for button in E.get('service_buttons',[]):
   q=xy(M.BW-button['x'],button['y']);rr=button['hole_d']*S/2
   d.ellipse((q[0]-rr,q[1]-rr,q[0]+rr,q[1]+rr),fill='#172931',outline='#bcc7cf',width=2)
   d.text((q[0]-rr-5,q[1]),'R' if button['ref']=='SW1' else 'B',font=f(12,True),fill='#eff4f7',anchor='rm')
  ub=E['update_button'];q=xy(M.BW-ub['x'],ub['y']);d.rounded_rectangle((q[0]-13,q[1]-14,q[0]+13,q[1]+14),radius=5,fill='#66757f',outline='#e4edf2',width=2);d.text((q[0]-18,q[1]-5),'UPDATE / C1',font=f(11),fill='#edf3f5',anchor='rm')
  d.text((bx+W/2,by+H-37),'PCB 当前布局示意 · 不是实装照片',font=f(13),fill='#e4eaf0',anchor='mt')
 # Slot drawn last: actual full-depth geometry.
 a=xy(M.LANYARD_RECT[0],M.LANYARD_RECT[1]);b=xy(M.LANYARD_RECT[2],M.LANYARD_RECT[3]);d.rounded_rectangle((*a,*b),radius=1.65*S,fill='#eef2f5',outline='#cbd3d8',width=2)
 d.text((bx+W/2,by-45),'正面 / 同一块六色屏' if side==0 else '背面 / 半透材料方向',font=f(22,True),fill='#264452',anchor='mt')
 # Front USB center aligns with canonical; rear mirrored.
 ux=M.C['usb']['center'] if side==0 else M.BW-M.C['usb']['center'];u=xy(ux,M.BOTTOM)
 d.rounded_rectangle((u[0]-7.5*S,u[1]-3,u[0]+7.5*S,u[1]+3),radius=3,fill='#23313b')
 yd=by+H+43;d.line((bx,yd,bx+W,yd),fill='#738792',width=2)
 for xx in (bx,bx+W):d.line((xx,yd-7,xx,yd+7),fill='#738792',width=2)
 d.text((bx+W/2,yd+8),f'66 mm × 109 mm  /  主壳 {M.FRONT-M.BACK:.1f} mm',font=f(19),fill='#506d7c',anchor='mt')
d.text((685,612),'内置门禁凭证',font=f(21,True),fill='#4f6877')
d.text((685,650),'类型与位置待确认',font=f(18),fill='#798d98')
d.line((78,1183,1622,1183),fill='#d5dfe4',width=2)
d.text((78,1206),'按真实 CAD 外形、固件预览与当前 PCB 布局绘制；半透质感为方向示意。未做实物装配或门禁兼容验证。',font=f(18),fill='#627b89')
im.save(OUT/'portrait_review_overview.png');print(OUT/'portrait_review_overview.png')
