
from pathlib import Path
import argparse,json,re,shutil,subprocess,tempfile
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description="Compile all production variants as C++14 with Clang CPU API stubs")
parser.add_argument("--clang",default=shutil.which("clang++"))
parser.add_argument("--report",type=Path,help="Optional JSON report path")
args=parser.parse_args()
if not args.clang: raise SystemExit("clang++ is unavailable")
directory=Path(tempfile.mkdtemp(prefix="rope_cpp14_"))
shutil.copytree(root/"tests/cpu_sim",directory/"cpu_sim")
header=directory/"cpu_sim/kernel_operator.h"
lines=header.read_text().splitlines(True)
stripped=0
for i,line in enumerate(lines):
 if line.startswith("inline ") and "(" not in line and line.rstrip().endswith(";"):
  lines[i]=line.removeprefix("inline ")
  stripped+=1
header.write_text("".join(lines))
source=(root/"kernel.asc").read_text()
launch=re.compile(
 r"rotary_pos_emb_draft<(?P<types>[^>]+)>"
 r"<<<cfg\.blockCount, nullptr, stream>>>"
 r"\(x, positions, y, (?P<config>cfg|compact)\);")
matches=list(launch.finditer(source))
assert len(matches)==10 and len({m["types"].replace(" ","") for m in matches})==10
source=launch.sub(lambda m:
 "{ ++sim::launches; for(sim::block=0;sim::block<cfg.blockCount;++sim::block) "
 "rotary_pos_emb_draft<"+m["types"]+">(x,positions,y,"+m["config"]+"); }",source)
tiny="rotary_pos_emb_one_token<<<tinyBlocks, nullptr, stream>>>(x, positions, y, tiny);"
assert source.count(tiny)==1
source=source.replace(tiny,
 "{ ++sim::launches; ++sim::tinyLaunches; for(sim::block=0;sim::block<tinyBlocks;++sim::block) "
 "rotary_pos_emb_one_token(x,positions,y,tiny); }")
assert "<<<" not in source
(directory/"kernel_cpu.inc").write_text(source)
command=[args.clang,"-std=c++14","-fsyntax-only","-Werror=c++17-extensions",
 "-Wall","-Wextra","-Werror","-Wno-unused-parameter","-I",str(directory/"cpu_sim"),
 "-I",str(directory),str(directory/"cpu_sim/driver.cpp")]
result=subprocess.run(command,capture_output=True,text=True)
report=dict(production_kernel="unchanged except CPU launch syntax adaptation",
 variants=11,cpu_stub_inline_variables_removed=stripped,
 command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
if args.report:
 args.report.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
raise SystemExit(result.returncode)
