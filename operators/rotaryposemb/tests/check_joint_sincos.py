import json
import argparse
from pathlib import Path
import numpy as np
F=np.float32
SC=[2.580631073747187e-7,2.1560553672307594e-5,1.160294554180584e-3,3.2251527327119334e-2,3.183098865345572e-1]
CC=[2.3889217773452806e-8,2.457805570135570e-6,1.726966512531477e-4,6.9616269567191625e-3,1.2900613822529625e-1,6.366197723507009e-1]
def poly(coeff,z):
 p=F(coeff[0])*z
 for c in coeff[1:-1]: p=(p+F(c))*z
 return p+F(coeff[-1])
def eval_trig(x):
 a=np.abs(x)
 w=(F(np.pi)-a)+F(-8.742277657347586e-8)
 u=(F(np.pi/2)-a)+F(-4.371138828673793e-8)
 z=a*w
 return (x*w)*poly(SC,z),u*poly(CC,z)
def reduce(x):
 q=np.rint(x*F(.15915494309189533577))
 return ((x-q*F(6.28125))-q*F(.001934051513671875))-q*F(1.2556659143567085e-6)
def measure(x,full=False):
 r=reduce(x) if full else x
 s,c=eval_trig(r)
 xx=x.astype(np.float64)
 return dict(count=int(x.size),sin_abs_error=float(np.max(abs(s-np.sin(xx)))),
 cos_abs_error=float(np.max(abs(c-np.cos(xx)))),
 max_reduced_abs=float(np.max(abs(r))),sin_exceeds_3e_7=int(np.sum(abs(s-np.sin(xx))>3e-7)),
 cos_exceeds_3e_7=int(np.sum(abs(c-np.cos(xx))>3e-7)))
parser=argparse.ArgumentParser(description="Validate FP32 joint sin/cos over 17 million angles")
parser.add_argument('--report',type=Path)
args=parser.parse_args()
records={}
records["uniform_reduced"]=measure(np.linspace(-np.pi,np.pi,4000001,dtype=F))
rng=np.random.default_rng(72629)
# random FP32, signed-domain uniform plus logarithmically distributed magnitudes and endpoints
random=np.concatenate([rng.uniform(-np.pi,np.pi,4000000).astype(F),
 (rng.uniform(-1,1,1000000)*2.**rng.uniform(-149,1,1000000)).astype(F),
 np.array([0.,-0.,np.pi,-np.pi,np.pi/2,-np.pi/2],dtype=F)])
records["random_reduced"]=measure(random)
records["uniform_raw"]=measure(np.linspace(0,131072,4000001,dtype=F),True)
records["random_raw"]=measure(rng.uniform(0,131072,4000000).astype(F),True)
report=dict(description="Separate FP32 Mul/Add emulation; float64 NumPy trig reference; no NPU timing or async validation",
 coeff_sin_descending=SC,coeff_cos_descending=CC,cases=records)
assert all(v["sin_exceeds_3e_7"] == 0 and v["cos_exceeds_3e_7"] == 0 for v in records.values())
if args.report:
 args.report.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
