"""Read only explicitly configured X accounts; never publish credentials or raw CLI output."""
import json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
ACCOUNTS=['biratori_koho','cfm_domingo','nanairohidaka','tonekkochannel1','tomatofarmerkao','niikappu_ta']
target=Path('data/x-posts.json')
def main():
    if not all(os.environ.get(k) for k in ('TWITTER_AUTH_TOKEN','TWITTER_CT0')):
        print('X credentials are not configured; keeping previous public data.')
        return
    previous=json.loads(target.read_text()) if target.exists() else {'items':[]}
    items=[];success=0
    for account in ACCOUNTS:
        try:
            result=subprocess.run(['twitter','search','--from',account,'--type','latest','-n','8','--json'],capture_output=True,text=True,timeout=60,check=True)
            rows=json.loads(result.stdout)
            if not isinstance(rows,list):raise ValueError('Invalid rows')
            for row in rows:
                if not isinstance(row,dict):continue
                author=row.get('author') or {}
                if str(author.get('screenName','')).lower()!=account.lower():continue
                post_id=str(row.get('id',''))
                if not re.fullmatch(r'\d+',post_id) or not isinstance(row.get('text'),str):continue
                items.append({'account':account,'text':row['text'],'link':f'https://x.com/{account}/status/{post_id}','pubDate':row.get('createdAtISO') or ''})
            success+=1
        except (subprocess.SubprocessError,ValueError,OSError):
            print(f'X retrieval failed for @{account}; retaining previous posts.')
            items.extend(i for i in previous.get('items',[]) if i.get('account')==account)
    if not success:
        print('No X accounts could be retrieved. Previous file retained.')
        sys.exit(1)
    items=sorted({i['link']:i for i in items}.values(),key=lambda i:i['pubDate'],reverse=True)
    payload={'status':'ok' if success==len(ACCOUNTS) else 'partial','generatedAt':datetime.now(timezone.utc).isoformat(),'accounts':ACCOUNTS,'items':items}
    temporary=target.with_suffix('.json.tmp');temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');temporary.replace(target)
    print(f'Updated {len(items)} X posts from {success} accounts.')
if __name__=='__main__':main()
