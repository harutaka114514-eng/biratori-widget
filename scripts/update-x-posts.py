"""Read only explicitly configured X accounts; never publish credentials or raw CLI output."""
import json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
ACCOUNTS=['biratori_koho','cfm_domingo','nanairohidaka','tonekkochannel1','tomatofarmerkao','niikappu_ta']
target=Path('data/x-posts.json')
def valid_avatar(url):
    if not isinstance(url,str):return False
    try:
        parsed=urlparse(url)
        return parsed.scheme=='https' and parsed.hostname=='pbs.twimg.com' and parsed.path.startswith('/profile_images/') and not parsed.username and not parsed.password
    except ValueError:return False

def refresh_avatars(items, previous):
    avatars={account:url for account,url in previous.get('avatars',{}).items() if account in ACCOUNTS and valid_avatar(url)}
    for account in ACCOUNTS:
        post=next((item for item in items if item.get('account')==account),None)
        if not post:continue
        post_id=post.get('link','').rsplit('/',1)[-1]
        if not re.fullmatch(r'\d+',post_id):continue
        try:
            with urlopen(f'https://cdn.syndication.twimg.com/tweet-result?id={post_id}&lang=ja&token=0',timeout=15) as response:
                user=json.load(response).get('user',{})
            url=user.get('profile_image_url_https')
            if user.get('screen_name','').lower()==account.lower() and valid_avatar(url):
                avatars[account]=url
        except (OSError,ValueError,AttributeError):
            print(f'X avatar retrieval failed for @{account}; retaining previous icon.')
    return avatars

def main():
    if not all(os.environ.get(k) for k in ('TWITTER_AUTH_TOKEN','TWITTER_CT0')):
        print('X credentials are not configured; keeping previous public data.')
        return
    previous=json.loads(target.read_text()) if target.exists() else {'items':[]}
    items=[];success=0
    for account in ACCOUNTS:
        try:
            result=subprocess.run(['twitter','user-posts',account,'-n','8','--json'],capture_output=True,text=True,timeout=60,check=True)
            rows=json.loads(result.stdout)
            if isinstance(rows,dict) and rows.get("ok") is True:
                rows=rows.get("data")
            if not isinstance(rows,list):raise ValueError('Invalid rows')
            for row in rows:
                if not isinstance(row,dict):continue
                author=row.get('author') or {}
                if str(author.get('screenName','')).lower()!=account.lower():continue
                post_id=str(row.get('id',''))
                if not re.fullmatch(r'\d+',post_id) or not isinstance(row.get('text'),str):continue
                images=[]
                for media in row.get('media') or []:
                    if not isinstance(media,dict) or media.get('type')!='photo':continue
                    url=media.get('url','')
                    parsed=urlparse(url)
                    if parsed.scheme=='https' and parsed.hostname=='pbs.twimg.com' and parsed.path.startswith('/media/'):
                        images.append(url)
                items.append({'images':images,'account':account,'text':row['text'],'link':f'https://x.com/{account}/status/{post_id}','pubDate':row.get('createdAtISO') or ''})
            success+=1
        except (subprocess.SubprocessError,ValueError,OSError) as error:
            # Print only fixed diagnostic labels, never subprocess output or credentials.
            raw=((getattr(error,'stderr','') or '')+' '+(getattr(error,'stdout','') or '')).lower()
            reason='unclassified'
            for terms,label in [(['401','403','authentication','expired','invalid cookie'],'authentication_or_access_denied'),(['429','rate limit'],'rate_limit'),(['timeout','timed out'],'timeout'),(['ssl','certificate'],'tls'),(['connection','resolve','network'],'network'),(['not found','404'],'endpoint_not_found')]:
                if any(term in raw for term in terms):reason=label;break
            if isinstance(error,ValueError):reason='invalid_response_format'
            if isinstance(error,FileNotFoundError):reason='tool_not_found'
            print(f'X diagnostic for @{account}: {reason}')
            print(f'X retrieval failed for @{account}; retaining previous posts.')
            items.extend(i for i in previous.get('items',[]) if i.get('account')==account)
    if not success:
        print('No X accounts could be retrieved. Previous file retained.')
        sys.exit(1)
    items=sorted({i['link']:i for i in items}.values(),key=lambda i:i['pubDate'],reverse=True)
    payload={'status':'ok' if success==len(ACCOUNTS) else 'partial','generatedAt':datetime.now(timezone.utc).isoformat(),'accounts':ACCOUNTS,'items':items,'avatars':refresh_avatars(items,previous)}
    temporary=target.with_suffix('.json.tmp');temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');temporary.replace(target)
    print(f'Updated {len(items)} X posts from {success} accounts.')
if __name__=='__main__':main()
