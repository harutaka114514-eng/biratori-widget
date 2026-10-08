import {mkdir,writeFile,rename} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {decodeXML,fetchText} from './update-daily-news.mjs';
export const categories={gourmet:'グルメ',money:'ライフスタイル',media:'ニュース',weather:'おでかけ'};
export function parseSasaruList(html,category){
  if(!Object.hasOwn(categories,category)||!html.includes('c-card__item'))throw Error('Unexpected SASARU category page');
  const items=[],seen=new Set();
  for(const match of html.matchAll(/<li\b[^>]*class="[^"]*\bc-card__item\b[^"]*"[^>]*>([\s\S]*?)<\/li>/gi)){
    const card=match[1],href=card.match(/href="([^\"]*\/article\/[^\"]+)"/)?.[1];
    const titleHTML=card.match(/<h3\b[^>]*class="[^"]*\bc-card__ttl\b[^"]*"[^>]*>([\s\S]*?)<\/h3>/i)?.[1];
    const date=card.match(/class="c-card__date"[^>]*>[\s\S]*?(20\d{2})\.(\d{1,2})\.(\d{1,2})/);
    if(!href||!titleHTML||!date)continue;
    const link=new URL(decodeXML(href),'https://sasaru.media/');
    if(link.hostname!=='sasaru.media'||!new RegExp('^/article/'+category+'/\\d{8}_\\d+/?$').test(link.pathname))continue;
    link.pathname=link.pathname.replace(/\/$/,'')+'/';
    if(seen.has(link.href))continue;
    const title=decodeXML(titleHTML.replace(/<[^>]+>/g,' ')).replace(/\s+/g,' ').trim();
    const pubDate=`${date[1]}-${date[2].padStart(2,'0')}-${date[3].padStart(2,'0')}T00:00:00+09:00`;
    if(!title||!Number.isFinite(Date.parse(pubDate)))continue;
    seen.add(link.href);items.push({title,link:link.href,pubDate,author:'SASARU',categories:[categories[category]],category});
  }
  if(!items.length)throw Error('SASARU article rows not found: '+category);
  return items;
}
export async function main(){
  const pages=await Promise.all(Object.keys(categories).map(async category=>parseSasaruList(await fetchText('https://sasaru.media/category/index.html?id='+category),category)));
  const items=pages.flat().sort((a,b)=>Date.parse(b.pubDate)-Date.parse(a.pubDate));
  const data={status:'ok',generatedAt:new Date().toISOString(),source:'SASARU公式カテゴリ一覧（ファッション除外）',items};
  await mkdir('data',{recursive:true});
  await writeFile('data/sasaru-news.json.tmp',JSON.stringify(data,null,2)+'\n');
  await rename('data/sasaru-news.json.tmp','data/sasaru-news.json');
  console.log('SASARUの記事を'+items.length+'件更新しました。');
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1])main().catch(error=>{console.error('SASARU取得失敗。前回データを保持します。 '+error.message);process.exitCode=1;});
