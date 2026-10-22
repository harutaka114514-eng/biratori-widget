import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {parseDomingoList,parseDomingoBackup} from '../scripts/update-domingo-news.mjs';
const now=Date.parse('2026-10-22T02:00:00Z');
function item({host='domingo.ne.jp',key='A',date='Wed, 21 Oct 2026 00:00:00 GMT'}={}){
  return `<item><title>架空の見出し - domingo.ne.jp</title><link>https://news.google.com/rss/articles/${key}?oc=5</link><pubDate>${date}</pubDate><source url="https://${host}">Domingo</source></item>`;
}
test('Domingo fallback requires matching publisher and a date within two weeks',()=>{
  const xml='<rss><channel>'+item()+item({host:'example.com',key:'B'})+item({date:'Wed, 01 Oct 2025 00:00:00 GMT',key:'C'})+item({date:'Fri, 23 Oct 2026 00:00:00 GMT',key:'D'})+'</channel></rss>';
  const result=parseDomingoBackup(xml,now);
  assert.equal(result.length,1);assert.equal(result[0].title,'架空の見出し');assert.equal(result[0].sourceHost,'domingo.ne.jp');
  assert.throws(()=>parseDomingoBackup('<html>maintenance</html>',now));
});
test('Direct list retains dated article parsing and rejects maintenance',()=>{
  const html='<ul class="card__list"><li><a href="https://domingo.ne.jp/article/123"><p class="card__title">架空の記事</p><p class="card__uploaddate">2026年10月21日</p></a></li></ul>';
  assert.equal(parseDomingoList(html,now)[0].link,'https://domingo.ne.jp/article/123');
  assert.throws(()=>parseDomingoList('<p>メンテナンス中</p>',now));
});
test('Browser accepts only verified Domingo fallback links and still excludes expired items',async()=>{
  const source=await readFile(new URL('../index.html',import.meta.url),'utf8');
  const filter=source.slice(source.indexOf('function filterDomingoArticles('),source.indexOf('async function preloadAllNews()'));
  const sandbox={Date:class extends Date{static now(){return now;}}};vm.createContext(sandbox);vm.runInContext(filter,sandbox);
  const valid={title:'架空',link:'https://news.google.com/rss/articles/ABC?oc=5',pubDate:'2026-10-21T00:00:00Z',sourceHost:'domingo.ne.jp'};
  assert.equal(sandbox.filterDomingoArticles([valid]).length,1);
  for(const patch of [{sourceHost:'evil.example'},{link:'https://news.google.com.evil.example/rss/articles/ABC'},{pubDate:'2025-01-01T00:00:00Z'}])assert.equal(sandbox.filterDomingoArticles([{...valid,...patch}]).length,0);
});
