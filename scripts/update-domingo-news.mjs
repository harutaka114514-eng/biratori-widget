import {mkdir,readFile,writeFile,rename} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {decodeXML,fetchText,parseFeed} from './update-daily-news.mjs';
const url='https://domingo.ne.jp/article/list/1';
const backupURL='https://news.google.com/rss/search?q=site%3Adomingo.ne.jp%2Farticle%2F%20when%3A14d&hl=ja&gl=JP&ceid=JP%3Aja';
export function parseDomingoBackup(xml,now=Date.now()){
  const allowed=new Set();
  for(const match of xml.matchAll(/<item\b[^>]*>([\s\S]*?)<\/item>/gi)){
    const source=match[1].match(/<source\b[^>]*url="([^"]+)"/i)?.[1];
    const link=match[1].match(/<link>([\s\S]*?)<\/link>/i)?.[1];
    try{if(new URL(decodeXML(source||'')).hostname==='domingo.ne.jp'&&link)allowed.add(decodeXML(link).trim());}catch{}
  }
  const items=parseFeed(xml,'Domingo',now,14*86400000).filter(item=>{
    const link=new URL(item.url);return allowed.has(item.url)&&link.protocol==='https:'&&link.hostname==='news.google.com'&&link.pathname.startsWith('/rss/articles/')&&Date.parse(item.publishedAt)<=now;
  }).map(item=>({title:item.title.replace(/\s+-\s+domingo\.ne\.jp$/i,''),link:item.url,pubDate:item.publishedAt,categories:['Domingo'],sourceHost:'domingo.ne.jp'}));
  if(!items.length)throw Error('Backup articles not found');
  return items;
}
export function parseDomingoList(html,now=Date.now()){
  const list=html.match(/<ul\b[^>]*class="card__list"[^>]*>([\s\S]*?)<\/ul>/i);
  if(!list)throw Error('Article list not found');
  const clean=value=>decodeXML(value.replace(/<[^>]+>/g,' ')).replace(/\s+/g,' ').trim();
  const seen=new Set(),items=[];
  for(const match of list[1].matchAll(/<li\b[^>]*>([\s\S]*?)<\/li>/gi)){
    const card=match[1],link=card.match(/<a\b[^>]*href="(https:\/\/domingo\.ne\.jp\/article\/\d+)"/i)?.[1];
    const title=card.match(/<p\b[^>]*class="card__title"[^>]*>([\s\S]*?)<\/p>/i)?.[1];
    const date=card.match(/<p\b[^>]*class="card__uploaddate"[^>]*>\s*(\d{4})年(\d{2})月(\d{2})日\s*<\/p>/i);
    if(!link||!title||!date||seen.has(link))continue;
    const pubDate=`${date[1]}-${date[2]}-${date[3]}T00:00:00+09:00`,time=Date.parse(pubDate);
    if(!Number.isFinite(time)||time>now||time<now-14*86400000)continue;
    seen.add(link);items.push({title:clean(title),link,pubDate,categories:['Domingo']});
  }
  if(!/card__uploaddate/.test(list[1]))throw Error('Article dates not found');
  return items.sort((a,b)=>Date.parse(b.pubDate)-Date.parse(a.pubDate));
}
export async function main(){
  const now=Date.now(),checkedAt=new Date(now).toISOString();let data;
  try{
    const items=parseDomingoList(await fetchText(url),now);
    data={status:'ok',generatedAt:checkedAt,checkedAt,source:'Domingo公式記事一覧（直近2週間）',sourceUrl:url,items};
  }catch(primary){
    try{
      const items=parseDomingoBackup(await fetchText(backupURL),now);
      data={status:'ok',generatedAt:checkedAt,checkedAt,source:'Domingo（Googleニュース経由・直近14日）',sourceUrl:backupURL,items,fallback:true,primaryError:primary.status?'HTTP '+primary.status:'公式一覧の取得失敗'};
    }catch{
      let previous={};try{previous=JSON.parse(await readFile('data/domingo-news.json','utf8'));}catch{}
      data={...previous,status:'error',checkedAt,error:primary.status?'HTTP '+primary.status:'公式一覧の取得失敗',items:previous.items||[]};
      process.exitCode=1;
    }
  }
  await mkdir('data',{recursive:true});
  await writeFile('data/domingo-news.json.tmp',JSON.stringify(data,null,2)+'\n');
  await rename('data/domingo-news.json.tmp','data/domingo-news.json');
  console.log(data.status==='ok'?data.source+'を'+data.items.length+'件更新しました。':'Domingoの公式・予備経路ともに取得失敗。保存済み記事を保持します。');
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1])main().catch(()=>{
  console.error('::warning title=Domingo記事の取得::公式一覧の取得に失敗しました。前回の記事を保持します。2週間を過ぎた記事は表示しません。');process.exitCode=1;
});
