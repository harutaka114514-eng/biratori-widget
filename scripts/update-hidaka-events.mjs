import {mkdir,writeFile,rename} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {decodeXML,fetchText} from './update-daily-news.mjs';
export const SOURCE_URL='https://hokkaido-hidaka-kankonavi.com/feed/';
const clean=v=>decodeXML(v).replace(/<[^>]*>/g,' ').normalize('NFKC').replace(/\s+/g,' ').trim();
const tag=(s,name)=>decodeXML(s.match(new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${name}>`,'i'))?.[1]||'').trim();
function dateKey(year,month,day){const d=new Date(Date.UTC(year,month-1,day));return d.getUTCFullYear()===year&&d.getUTCMonth()===month-1&&d.getUTCDate()===day?`${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`:null;}
export function eventDates(title,text,publishedAt){
  const normalized=clean(text),heading=normalized.match(/開催(?:日時|期間|日程)\s*[:：]?\s*([\s\S]*?)(?=場所|会場|お問い合わせ|$)/)?.[1];
  const yearFromPublication=Number(new Date(publishedAt).toLocaleDateString('sv-SE',{timeZone:'Asia/Tokyo'}).slice(0,4));
  if(!Number.isFinite(yearFromPublication))return null;
  let year=yearFromPublication,month=0;const dates=[];
  for(const m of (heading||normalized).matchAll(/(?:(20\d{2})年\s*|令和\s*(\d+)年(?:度)?\s*)?(\d{1,2})月\s*(\d{1,2})日/g)){
    const next=Number(m[3]);if(m[1]||m[2])year=m[1]?Number(m[1]):2018+Number(m[2]);else if(month&&next<month)year++;
    month=next;const key=dateKey(year,month,Number(m[4]));if(key)dates.push(key);if(dates.length===2)break;
  }
  // Titles often contain a compact range, including a day-only range end.
  const t=clean(title),range=t.match(/(\d{1,2})\/(\d{1,2})(?:\s*[（(][^）)]*[）)])?\s*[~〜～―-]\s*(?:(\d{1,2})\/)?(\d{1,2})/);
  if(range&&dates.length<2){const y=dates.length?Number(dates[0].slice(0,4)):yearFromPublication;const sm=Number(range[1]),em=Number(range[3]||range[1]);const start=dateKey(y,sm,Number(range[2])),end=dateKey(y+(em<sm?1:0),em,Number(range[4]));if(start&&end)return {startDate:start,endDate:end};}
  if(!dates.length){const m=t.match(/(\d{1,2})\/(\d{1,2})/);if(m){const key=dateKey(yearFromPublication,Number(m[1]),Number(m[2]));if(key)dates.push(key);}}
  if(!dates.length)return null;
  return {startDate:dates[0],endDate:dates.at(-1)};
}
export function parseHidakaEvents(xml,now=Date.now()){
  if(!/<rss\b/i.test(xml)||!/<channel\b/i.test(xml))throw Error('Invalid RSS');
  const today=new Date(now).toLocaleDateString('sv-SE',{timeZone:'Asia/Tokyo'}),items=[],seen=new Set();let skipped=0;
  for(const m of xml.matchAll(/<item(?:\s[^>]*)?>([\s\S]*?)<\/item>/gi)){
    const raw=m[1],categories=[...raw.matchAll(/<category(?:\s[^>]*)?>([\s\S]*?)<\/category>/gi)].map(x=>clean(x[1]));
    if(!categories.includes('イベント'))continue;
    const title=clean(tag(raw,'title')),link=tag(raw,'link'),publishedAt=tag(raw,'pubDate'),text=clean(tag(raw,'content:encoded')||tag(raw,'description'));
    if(!title||!/^https:\/\/hokkaido-hidaka-kankonavi\.com\/information\/\d+\/$/.test(link)||seen.has(link))continue;
    const dates=eventDates(title,text,publishedAt);if(!dates||dates.endDate<dates.startDate){skipped++;continue;}if(dates.endDate<today)continue;
    const venue=text.match(/(?:場所|会場)(?:\s+|[:：]\s*)(.*?)(?=お問い合わせ|問い合わせ|$)/)?.[1]?.trim();
    const towns=['平取町','日高町','新冠町','新ひだか町','浦河町','様似町','えりも町','苫小牧市'].filter(t=>(title+' '+text).includes(t));
    const location=venue?venue.slice(0,160):towns.length>2?'日高地域（平取町ほか）':towns.join('・')||'会場は配信元で確認';
    seen.add(link);items.push({title,link,...dates,location,publishedAt:new Date(publishedAt).toISOString()});
  }
  items.sort((a,b)=>Number(!a.location.includes('平取'))-Number(!b.location.includes('平取'))||a.endDate.localeCompare(b.endDate)||a.startDate.localeCompare(b.startDate));
  return {items,skipped};
}
export async function main(){
  const now=Date.now(),{items,skipped}=parseHidakaEvents(await fetchText(SOURCE_URL),now);
  const data={status:'ok',generatedAt:new Date(now).toISOString(),source:'北海道ひだか観光ナビ',sourceUrl:SOURCE_URL,items};
  await mkdir('data',{recursive:true});await writeFile('data/hidaka-events.json.tmp',JSON.stringify(data,null,2)+'\n');await rename('data/hidaka-events.json.tmp','data/hidaka-events.json');
  console.log(`日高の催しを${items.length}件更新。開催日を確認できない記事は${skipped}件除外。`);
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1])main().catch(()=>{console.error('::warning title=日高の催し::RSSの取得に失敗しました。前回の情報を保持します。');process.exitCode=1;});
