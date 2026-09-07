
from pathlib import Path
import argparse,json,tempfile
import numpy as np
import run_cpu_kernel as cpu
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description="Validate one-token dispatch, DMA, events and strict FP32 output")
parser.add_argument("--baseline",type=Path,help="Optional kernel.asc for additional bitwise comparison")
parser.add_argument("--report",type=Path,help="Optional JSON report path")
args=parser.parse_args()
run,_=cpu.build()
baseline=None
if args.baseline:
 base=Path(tempfile.mkdtemp(prefix="rope_tiny_base_"))
 (base/"kernel.asc").write_text(args.baseline.read_text())
 cpu.ROOT=base
 try:
  baseline,_=cpu.build()
 finally:
  cpu.ROOT=root
rng=np.random.default_rng(71292)
thetas=[float(np.nextafter(np.float32(0),np.float32(1))),1e-6,.25,.5,.999,1.,1.001,10000.,1e38]
counts=[1,2,3,4,7,8,15,16,17,31,32,33,63,64,65,127,128]
records=[];tiny=generic=0
for tokens in counts:
 for cores in sorted({1,max(1,tokens-1),tokens,tokens+1}):
  for theta in thetas:
   for pattern in ("zero","range"):
    shape=(1,tokens,1,16)
    x=rng.uniform(-10,10,shape).astype(np.float32)
    pos=np.zeros(shape[:2],dtype=np.int32)
    if pattern=="range":
     pos[:]=rng.integers(-131072,131073,shape[:2],dtype=np.int32)
     pos.flat[0]=131072
     if tokens>1:pos.flat[1]=-131072
     if tokens>2:pos.flat[2]=0
    y=np.full(shape,12345,dtype=np.float32)
    old=np.full(shape,12345,dtype=np.float32)
    assert run(x.ctypes.data,pos.ctypes.data,y.ctypes.data,*shape,0,cores,theta)==0
    selected=int(run.tiny_count())
    stats=np.zeros(18,dtype=np.uint64);run.tiny_stats(stats.ctypes.data)
    expected=tokens<=cores
    assert selected==int(expected),(tokens,cores,theta,selected)
    if expected:
     assert np.array_equal(stats[:6],[2*tokens,tokens,68*tokens,64*tokens,tokens,0]),stats
     wanted=np.array([tokens*(1+int(theta<1)),tokens,tokens*int(theta<1),tokens,tokens,tokens])
     assert np.array_equal(stats[6:12],wanted),(stats,wanted)
     assert np.array_equal(stats[12:18],wanted),(stats,wanted)
     tiny+=1
    else:generic+=1
    if baseline:
     assert baseline(x.ctypes.data,pos.ctypes.data,old.ctypes.data,*shape,0,cores,theta)==0
     assert np.array_equal(y.view(np.uint32),old.view(np.uint32)),(tokens,cores,theta,pattern)
    with np.errstate(all="ignore"):
     mismatch,error=cpu.comparison(y,cpu.powf_reference(x,pos,theta),np.float32)
    assert mismatch<=1e-4,(tokens,cores,theta,pattern,mismatch,error)
    assert not np.any(y==12345)
    records.append(dict(tokens=tokens,cores=cores,theta=theta,pattern=pattern,
      tiny=bool(expected),mismatch=mismatch,max_error=error))
# Flattened batch indexing and close but intentionally unselected shape/dtype paths.
extras=[((2,7,1,16),np.float32,14),((3,5,1,16),np.float32,16),
 ((7,1,1,16),np.float32,8),((1,7,1,16),np.float16,8),
 ((1,7,2,16),np.float32,8),((1,7,1,18),np.float32,8),
 ((2,7,1,16),np.float32,13)]
for shape,dtype,cores in extras:
 for theta in (.5,1.,10000.):
  x=rng.uniform(-10,10,shape).astype(dtype)
  pos=rng.integers(-131072,131073,shape[:2],dtype=np.int32)
  y=np.full(shape,12345,dtype=dtype);old=np.full(shape,12345,dtype=dtype)
  assert run(x.ctypes.data,pos.ctypes.data,y.ctypes.data,*shape,int(dtype==np.float16),cores,theta)==0
  expected=dtype==np.float32 and shape[2:]==(1,16) and shape[0]*shape[1]<=cores
  assert int(run.tiny_count())==int(expected)
  if baseline:
   assert baseline(x.ctypes.data,pos.ctypes.data,old.ctypes.data,*shape,int(dtype==np.float16),cores,theta)==0
   assert np.array_equal(y.view(np.uint8),old.view(np.uint8))
  mismatch,error=cpu.comparison(y,cpu.powf_reference(x,pos,theta),dtype)
  assert mismatch<=1e-4
  assert not np.any(y==12345)
  tiny+=int(expected);generic+=int(not expected)
  records.append(dict(shape=shape,dtype=np.dtype(dtype).name,cores=cores,theta=theta,
   tiny=bool(expected),mismatch=mismatch,max_error=error))
report=dict(cases=len(records),tiny_selected=tiny,generic_selected=generic,
 baseline_output="all bitwise identical" if baseline else "not requested",strict_reference="passed",
 copy_per_tiny_core={"input_calls":2,"input_bytes":68,"output_calls":1,"output_bytes":64},
 tiny_tbuf_init_per_core=1,tiny_tque_init_per_core=0,
 explicit_event_pair_counts="all passed including wide PH V_S/S_V",
 records=records)
if args.report:
 args.report.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({k:v for k,v in report.items() if k!="records"},indent=2))
