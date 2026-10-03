import {mkdir,writeFile,rename} from 'node:fs/promises';
import {parseFeed,fetchText} from './update-daily-news.mjs';

const url='https://news.google.com/rss/search?q=site%3Adomingo.ne.jp&hl=ja&gl=JP&ceid=JP%3Aja';
try{
  const now=Date.now();
  const candidates=parseFeed(await fetchText(url),'Domingo',now,90*86400000);
  const seen=new Set();
  const items=candidates.sort((a,b)=>Date.parse(b.publishedAt)-Date.parse(a.publishedAt)).filter(item=>{if(seen.has(item.url))return false;seen.add(item.url);return true;}).slice(0,30).map(item=>({title:item.title,link:item.url,pubDate:item.publishedAt,categories:['Domingo']}));
  if(!items.length)throw Error('No articles');
  const data={status:'ok',generatedAt:new Date(now).toISOString(),source:'Googleニュース経由のDomingo記事',items};
  await mkdir('data',{recursive:true});
  await writeFile('data/domingo-news.json.tmp',JSON.stringify(data,null,2)+'\n');
  await rename('data/domingo-news.json.tmp','data/domingo-news.json');
  console.log('Domingo記事を'+items.length+'件更新しました。AIとRSS変換サービスは使いません。');
}catch{
  console.error('::warning title=Domingo記事の取得::取得に失敗しました。前回のDomingo記事を保持します。');
  process.exitCode=1;
}
