import {mkdir,writeFile,rename} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {decodeXML,fetchText} from './update-daily-news.mjs';
export const sourceUrl='https://www.walkerplus.com/article_list/ar0101/ag0007/';
export function parseWalkerList(html){
  if(!/<h1\b[^>]*>[^<]*北海道のおでかけのニュース一覧/.test(html))throw Error('Unexpected Walker page');
  const clean=value=>decodeXML(value.replace(/<[^>]+>/g,' ')).replace(/\s+/g,' ').trim();
  const items=[],seen=new Set();
  for(const match of html.matchAll(/<li\b[^>]*class="[^"]*\bm-newslist__item\b[^"]*"[^>]*>([\s\S]*?)<\/li>/gi)){
    const card=match[1];
    const anchor=card.match(/<a\b[^>]*class="[^"]*\bm-newslist__ttl\b[^"]*"[^>]*>([\s\S]*?)<\/a>/i);
    const href=anchor?.[0].match(/href="([^"]+)"/i)?.[1];
    const date=card.match(/<time\b[^>]*>\s*(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日/);
    if(!anchor||!href||!date)continue;
    const link=new URL(href,sourceUrl);
    if(link.hostname!=='www.walkerplus.com'||!/^\/article\/\d+\/$/.test(link.pathname)||seen.has(link.href))continue;
    const title=clean(anchor[1]),pubDate=`${date[1]}-${date[2].padStart(2,'0')}-${date[3].padStart(2,'0')}T00:00:00+09:00`;
    if(!title||!Number.isFinite(Date.parse(pubDate)))continue;
    seen.add(link.href);items.push({title,link:link.href,pubDate,author:'ウォーカープラス',categories:['北海道','おでかけ']});
  }
  if(!items.length)throw Error('Walker article rows not found');
  return items.sort((a,b)=>Date.parse(b.pubDate)-Date.parse(a.pubDate));
}
export async function main(){
  const items=parseWalkerList(await fetchText(sourceUrl));
  const data={status:'ok',generatedAt:new Date().toISOString(),source:'ウォーカープラス北海道おでかけ',sourceUrl,items};
  await mkdir('data',{recursive:true});
  await writeFile('data/walker-news.json.tmp',JSON.stringify(data,null,2)+'\n');
  await rename('data/walker-news.json.tmp','data/walker-news.json');
  console.log(`北海道おでかけ記事を${items.length}件更新しました。`);
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1])main().catch(e=>{
  console.error('::warning::ウォーカープラスの更新に失敗しました。前回の記事を保持します。 '+e.message);process.exitCode=1;
});
