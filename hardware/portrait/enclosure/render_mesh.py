"""Small orthographic, depth-buffered renderer for actual OCC triangles.

Unlike a painter's 3D plot, per-pixel depth preserves openings/occlusion.
This is an engineering preview, not photorealistic hardware evidence.
"""
import math
import numpy as np
from PIL import Image,ImageDraw,ImageFont


def render_shapes(items,output_path,title='CAD',elevation=55,azimuth=-62):
    W,H=1250,1300
    all_points=[]; all_tris=[]; all_colors=[]
    def rgb(s):return np.array([int(s[i:i+2],16) for i in (1,3,5)],dtype=float)
    for shape,color in items:
        points,tris=shape.tessellate(0.06,0.12)
        points=np.array([[v.x,v.y,v.z] for v in points]);offset=len(all_points)
        all_points.extend(points);all_tris.extend([[v+offset for v in t] for t in tris]);all_colors.extend([rgb(color)]*len(tris))
    points=np.array(all_points)
    er,ar=math.radians(elevation),math.radians(azimuth)
    view=np.array([math.cos(er)*math.cos(ar),math.cos(er)*math.sin(ar),math.sin(er)])
    up_hint=np.array([0.,1.,0.]);right=np.cross(up_hint,view);right/=np.linalg.norm(right)
    up=np.cross(view,right);up/=np.linalg.norm(up)
    projected=points@np.array([right,up,view]).T
    lo=projected[:,:2].min(axis=0);hi=projected[:,:2].max(axis=0)
    scale=min((W-130)/(hi[0]-lo[0]),(H-210)/(hi[1]-lo[1]))
    projected[:,0]=(projected[:,0]-(lo[0]+hi[0])/2)*scale+W/2
    projected[:,1]=-(projected[:,1]-(lo[1]+hi[1])/2)*scale+(H+70)/2
    pixels=np.full((H,W,3),[239,243,247],dtype=np.uint8)
    depth=np.full((H,W),-np.inf)
    light=np.array([-.25,.5,.85]);light/=np.linalg.norm(light)
    for inds,color in zip(all_tris,all_colors):
        p=projected[inds];q=points[inds]
        x0=max(0,int(math.floor(p[:,0].min())));x1=min(W-1,int(math.ceil(p[:,0].max())))
        y0=max(0,int(math.floor(p[:,1].min())));y1=min(H-1,int(math.ceil(p[:,1].max())))
        if x0>x1 or y0>y1:continue
        den=(p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
        if abs(den)<1e-8:continue
        xx,yy=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
        a=((p[1,1]-p[2,1])*(xx-p[2,0])+(p[2,0]-p[1,0])*(yy-p[2,1]))/den
        b=((p[2,1]-p[0,1])*(xx-p[2,0])+(p[0,0]-p[2,0])*(yy-p[2,1]))/den
        c=1-a-b
        zz=a*p[0,2]+b*p[1,2]+c*p[2,2]
        mask=(a>=-1e-8)&(b>=-1e-8)&(c>=-1e-8)&(zz>depth[y0:y1+1,x0:x1+1])
        normal=np.cross(q[1]-q[0],q[2]-q[0]);n=np.linalg.norm(normal)
        shade=.60+.40*abs(np.dot(normal/n,light)) if n else .8
        pixels[y0:y1+1,x0:x1+1][mask]=np.clip(color*shade,0,255).astype(np.uint8)
        depth[y0:y1+1,x0:x1+1][mask]=zz[mask]
    im=Image.fromarray(pixels)
    d=ImageDraw.Draw(im)
    f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',23)
    d.text((W/2,35),title,font=f,fill='#253b50',anchor='mt')
    d.text((W/2,H-42),'Actual CAD mesh | prototype only | no physical fit/RF validation',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18),fill='#60788f',anchor='mt')
    im.save(output_path)
