import json, urllib.request
base='https://www.jma.go.jp'
def get(url):
    request=urllib.request.Request(base+url,headers={'Origin':'https://harutaka114514-eng.github.io','User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(request,timeout=25) as r:
        body=r.read()
        print('SOURCE',url,'HTTP',r.status,'CORS',r.headers.get('Access-Control-Allow-Origin'),'SIZE',len(body))
        return body
area=json.loads(get('/bosai/common/const/area.json'))
for group, records in area.items():
    if isinstance(records,dict):
        for code, obj in records.items():
            if isinstance(obj,dict) and ('平取' in obj.get('name','') or '胆振' in obj.get('name','') or '日高' == obj.get('name','')):
                print('AREA',group,code,json.dumps(obj,ensure_ascii=False))
data=json.loads(get('/bosai/warning/data/r8/015000.json'))
open('/tmp/biratori-jma.json','w',encoding='utf-8').write(json.dumps(data,ensure_ascii=False))
print('TYPE',type(data).__name__)
if isinstance(data,list):
    for report in data:
        print('REPORT',json.dumps({k:v for k,v in report.items() if k!='warning'},ensure_ascii=False)[:2500])
        print('CITY',json.dumps([i for i in report.get('warning',{}).get('class20Items',[]) if i.get('areaCode')=='0160200'],ensure_ascii=False)[:12000])
