import {mkdir,writeFile,rename} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {decodeXML,fetchText} from './update-daily-news.mjs';
export const SOURCE_URL='https://www.town.biratori.hokkaido.jp/soshikikarasagasu/chominka/seikatsukankyokakari/1/1/2/323.html';
const clean=v=>decodeXML(String(v||'')).replace(/<[^>]*>/g,' ').normalize('NFKC').replace(/\s+/g,' ').trim();
function dateKey(year,month,day){const d=new Date(Date.UTC(year,month-1,day));return d.getUTCFullYear()===year&&d.getUTCMonth()===month-1&&d.getUTCDate()===day?`${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`:null;}
// 平取町公式ページの「平取町のヒグマ出没情報（令和N年度）」表を読む。
// 年度は4月始まりなので、1〜3月の月日は翌暦年に属する。
export function parseBearSightings(html){
  if(typeof html!=='string'||!html.includes('ヒグマ出没情報'))throw Error('Invalid bear sightings page');
  const fy=html.match(/平取町のヒグマ出没情報（令和\s*(\d+)\s*年度）/);
  if(!fy)throw Error('Fiscal year heading not found');
  const fiscalYear=Number(fy[1]),baseYear=2018+fiscalYear;
  const asOfMatch=clean(html).match(/令和\s*(\d+)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日現在/);
  const asOf=asOfMatch?dateKey(2018+Number(asOfMatch[1]),Number(asOfMatch[2]),Number(asOfMatch[3])):null;
  const mapHref=[...html.matchAll(/href="([^"]+)"/gi)].map(m=>decodeXML(m[1])).find(u=>/google\.com\/maps\/d\//.test(u));
  const items=[],seen=new Set();
  for(const row of html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/gi)){
    const cells=[...row[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi)].map(m=>clean(m[1]));
    if(cells.length<4||!/^\d+$/.test(cells[0]))continue;
    const dm=cells[1].match(/(\d{1,2})月\s*(\d{1,2})日/);
    if(!dm)continue;
    const month=Number(dm[1]),date=dateKey(month>=4?baseYear:baseYear+1,month,Number(dm[2]));
    if(!date)continue;
    const item={date,time:cells[2]||'不明',place:cells[3],note:cells[4]||''};
    const key=[item.date,item.time,item.place].join('|');
    if(seen.has(key))continue;
    seen.add(key);items.push(item);
  }
  if(!items.length)throw Error('No bear sighting rows found');
  items.sort((a,b)=>b.date.localeCompare(a.date));
  return {fiscalYearLabel:`令和${fiscalYear}年度`,asOf,mapUrl:mapHref||null,items};
}
export async function main(){
  const now=Date.now(),parsed=parseBearSightings(await fetchText(SOURCE_URL));
  const data={status:'ok',generatedAt:new Date(now).toISOString(),source:'平取町',sourceUrl:SOURCE_URL,...parsed};
  await mkdir('data',{recursive:true});await writeFile('data/bear-sightings.json.tmp',JSON.stringify(data,null,2)+'\n');await rename('data/bear-sightings.json.tmp','data/bear-sightings.json');
  console.log(`平取町のヒグマ出没情報を${parsed.items.length}件更新。最新は${parsed.items[0].date} ${parsed.items[0].place}。`);
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1])main().catch(()=>{console.error('::warning title=ヒグマ出没情報::平取町ページの取得・解析に失敗しました。前回の情報を保持します。');process.exitCode=1;});
