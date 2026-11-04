import json,re
from pathlib import Path
folder=Path(__file__).resolve().parent
shots=folder.parent/'shots'
repo=Path('/Users/couttsj/Documents/_code/pythonMANIC')
path=folder/'review.md'
s=path.read_text()
def link_source(m):
    target,line=m.group(1),m.group(2)
    p=repo/target
    assert p.exists(),p
    assert int(line)<=len(p.read_text().splitlines()),(p,line)
    return '['+p.name+':'+line+']('+str(p)+':'+line+')'
s=re.sub(r'`(src/[^`]+?):(\d+)`',link_source,s)
def link_shot(m):
    name=m.group(1)
    p=shots/name if (shots/name).exists() else folder/name
    assert p.exists(),p
    return '['+name+']('+str(p)+')'
s=re.sub(r'`([^`/]+\.png)`',link_shot,s)
path.write_text(s)
scoring=json.loads(re.search(r'```json\n([^\n]+)\n```\s*$',s).group(1))
assert round(sum(scoring['F'+str(i)] for i in range(1,9))/8,1)==scoring['overall']
assert len(re.findall(r'^\d+\. \*\*',s,re.M))==12
assert s.count('```')==2
assert '\u2014' not in s
print('report_verified',json.dumps({'scores':scoring,'issues':12,'supplied_images':len(list(shots.glob('*.png'))),'words':len(s.split()),'file':str(path)}))
