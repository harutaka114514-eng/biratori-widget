import {mkdir,readFile,writeFile,rename} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {decodeXML,fetchText} from './update-daily-news.mjs';
export const SOURCE_URL='https://www.gutabi.jp/event/area?w%5Bsp_i__a%5D%5B%5D=5&w%5Bsp_i__a%5D%5B%5D=9&button=';
const clean=value=>decodeXML(value.replace(/<[^>]*>/g,'')).normalize('NFKC').replace(/\s+/g,' ').trim();
const field=(html,tag)=>clean(html.match(new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)<\\/${tag}>`,'i'))?.[1]||'');
function dateKey(year,month,day){const d=new Date(Date.UTC(year,month-1,day));if(d.getUTCFullYear()!==year||d.getUTCMonth()!==month-1||d.getUTCDate()!==day)throw Error('Invalid event date');return `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`;}
export function parseGutabiEvents(html,expectedMonth){
  const heading=html.match(/<h2\b[^>]*>\s*(20\d{2})年(\d{1,2})月のイベント\s*<\/h2>/);
  if(!heading||`${heading[1]}-${heading[2].padStart(2,'0')}`!==expectedMonth||!html.includes('mod__item__list19__wrap'))throw Error('Unrecognized event calendar');
  const calendarYear=Number(heading[1]),calendarMonth=Number(heading[2]),items=[];let skipped=0;
  for(const match of html.matchAll(/<li\b[^>]*class="[^"]*\bmod__item__list19\b[^"]*"[^>]*>([\s\S]*?)<\/li>/gi)){
    const card=match[1],id=card.match(/href="\/event\/detail\/(\d+)\/?"/)?.[1],title=field(card,'h3');
    const location=clean(card.match(/<p\b[^>]*class="cat\b[^"]*"[^>]*>([\s\S]*?)<\/p>/)?.[1]||'');
    const dateLabel=field(card.match(/<p\b[^>]*class="day"[^>]*>([\s\S]*?)<\/p>/)?.[1]||'','b');
    if(!id||!title||!location||!dateLabel)throw Error('Incomplete event card');
    if(/中止/.test(title+' '+dateLabel)){skipped++;continue;}
    const tokens=[...dateLabel.matchAll(/(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日/g)];
    if(!tokens.length){skipped++;continue;}
    const first=tokens[0],last=tokens.at(-1);let startYear=Number(first[1]||calendarYear);
    if(!first[1]&&Number(first[2])>calendarMonth&&Number(last[2])<=calendarMonth)startYear--;
    const startDate=dateKey(startYear,Number(first[2]),Number(first[3]));
    let endMonth=Number(last[2]),endDay=Number(last[3]);
    // A compact end such as 10月2日〜4日 inherits the start month.
    const compact=dateLabel.match(/[~〜～―–-]\s*(\d{1,2})日/);if(tokens.length===1&&compact)endDay=Number(compact[1]);
    const endYear=Number(last[1]||startYear+(endMonth<Number(first[2])?1:0));
    const endDate=dateKey(endYear,endMonth,endDay);if(endDate<startDate)throw Error('Reversed event dates');
    items.push({title,link:`https://www.gutabi.jp/event/detail/${id}`,startDate,endDate,location,dateLabel,source:'ぐうたび北海道'});
  }
  if(!items.length&&!skipped&&!/<ul\b[^>]*class="[^"]*mod__item__list19__wrap[^"]*"[^>]*>\s*<\/ul>/.test(html))throw Error('Calendar unexpectedly empty');
  return {items,skipped};
}
export async function main(){
  const now=new Date(),month=now.toLocaleDateString('sv-SE',{timeZone:'Asia/Tokyo'}).slice(0,7),path='data/gutabi-events.json';
  try{const previous=JSON.parse(await readFile(path,'utf8'));if(!process.argv.includes('--force')&&previous.status==='ok'&&previous.month===month){console.log('ぐうたび：今月の情報は取得済みです。');return;}}catch{}
  // Explicit month URLs keep the requested year clear, including at year boundaries.
  const next=new Date(Date.UTC(Number(month.slice(0,4)),Number(month.slice(5)),1)).toISOString().slice(0,7);
  const records=[];
  for(const key of [month,next]){
    const url=SOURCE_URL.replace('/area?','/area/'+key.replace('-','')+'?');
    records.push(parseGutabiEvents(await fetchText(url),key));
  }
  const seen=new Set(),items=records.flatMap(record=>record.items).filter(item=>{const key=item.link+'|'+item.startDate;if(seen.has(key))return false;seen.add(key);return true;}).sort((a,b)=>a.startDate.localeCompare(b.startDate)||a.title.localeCompare(b.title,'ja'));
  const data={status:'ok',generatedAt:now.toISOString(),month,source:'ぐうたび北海道',sourceUrl:SOURCE_URL,items};
  await mkdir('data',{recursive:true});await writeFile(path+'.tmp',JSON.stringify(data,null,2)+'\n');await rename(path+'.tmp',path);
  console.log(`ぐうたび：今月・来月の催しを${items.length}件取得、日程未定・中止は${records.reduce((n,r)=>n+r.skipped,0)}件除外。`);
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1])main().catch(error=>{console.error('::warning title=ぐうたびの催し::取得できなかったため前回の情報を保持します。 '+error.message);process.exitCode=1;});
