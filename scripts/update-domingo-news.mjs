import {mkdir,writeFile,rename} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {decodeXML,fetchText} from './update-daily-news.mjs';
const url='https://domingo.ne.jp/article/list/1';
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
  const now=Date.now(),items=parseDomingoList(await fetchText(url),now);
  const data={status:'ok',generatedAt:new Date(now).toISOString(),source:'Domingo公式記事一覧（直近2週間）',sourceUrl:url,items};
  await mkdir('data',{recursive:true});
  await writeFile('data/domingo-news.json.tmp',JSON.stringify(data,null,2)+'\n');
  await rename('data/domingo-news.json.tmp','data/domingo-news.json');
  console.log('Domingo公式一覧の直近2週間の記事を'+items.length+'件更新しました。');
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1])main().catch(()=>{
  console.error('::warning title=Domingo記事の取得::公式一覧の取得に失敗しました。前回の記事を保持します。2週間を過ぎた記事は表示しません。');process.exitCode=1;
});
