import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const source=html.split('// BEGIN_LIVE_VIDEO_PLAYER')[1].split('// END_LIVE_VIDEO_PLAYER')[0];
function fixture(settings={}){
  const nodes=new Map();
  for(const id of ['main-video','video-watch-link','video-status','btn-v1','btn-stv','btn-custom-video'])nodes.set(id,{src:'',href:'',textContent:'',classList:{add(){},remove(){}}});
  const timers=[],scripts=[];
  const context=vm.createContext({widgetSettings:settings,Date,URL,URLSearchParams,location:{origin:'https://harutaka114514-eng.github.io'},window:{},setTimeout:fn=>(timers.push(fn),timers.length),clearTimeout(){},loadWidgetFeedData:async()=>({}),document:{getElementById:id=>nodes.get(id),querySelectorAll:()=>[],createElement:()=>({}),head:{append:script=>scripts.push(script)}}});
  vm.runInContext(source,context);
  return {context,nodes,timers,scripts,run:code=>vm.runInContext(code,context)};
}
test('Retired saved default follows verified live metadata; custom video is preserved',()=>{
  const f=fixture({videos:{'btn-stv':'3xfwDdlulDY'}});
  f.run("switchVideo('', 'btn-stv')");
  assert.match(f.nodes.get('main-video').src,/Wvqa1Csp5Vk/);
  f.run("updateLiveVideoSources({'btn-stv':{status:'ok',videoId:'NEW12345678',generatedAt:'2026-11-03T09:00:00Z'}})");
  assert.match(f.nodes.get('main-video').src,/NEW12345678/);
  f.context.widgetSettings.videos['btn-stv']='CUSTOM12345';
  f.run("switchVideo('', 'btn-stv')");
  assert.match(f.nodes.get('main-video').src,/CUSTOM12345/);
  f.run("updateLiveVideoSources({'btn-stv':{status:'error',videoId:'BAD12345678'}})");
  assert.match(f.nodes.get('main-video').src,/CUSTOM12345/);
});
test('Video embeds set origin, preserve direct viewing, and explain a blocked player',()=>{
  const f=fixture();f.run("switchVideo('', 'btn-v1')");
  assert.equal(new URL(f.nodes.get('main-video').src).searchParams.get('origin'),'https://harutaka114514-eng.github.io');
  assert.equal(f.nodes.get('video-watch-link').href,'https://www.youtube.com/watch?v=tvgbZZYS4Nk');
  assert.equal(f.scripts[0].src,'https://www.youtube.com/iframe_api');
  f.timers[0]();assert.match(f.nodes.get('video-status').textContent,/YouTubeで開いて/);
  assert.match(html,/allow="autoplay; encrypted-media; picture-in-picture; fullscreen"/);
});
test('Player errors are visible; a successful playback clears the error',()=>{
  const f=fixture();let events;
  f.context.window.YT={Player:class{constructor(id,options){events=options.events;}mute(){}loadVideoById(){}}};
  f.run("switchVideo('', 'btn-stv')");
  events.onError({data:100});assert.match(f.nodes.get('video-status').textContent,/この動画は再生できません/);
  events.onStateChange({data:1});assert.equal(f.nodes.get('video-status').textContent,'');
  events.onAutoplayBlocked();assert.match(f.nodes.get('video-status').textContent,/再生ボタン/);
});
test('Murash tab does not display an unrelated RSS loading status',()=>{
  const status={textContent:'取得中…'};
  const fn=html.slice(html.indexOf('function renderNewsStatus('),html.indexOf('function isDomingoFeed('));
  vm.runInNewContext(fn+"renderNewsStatus('murash');",{document:{getElementById:()=>status}});
  assert.equal(status.textContent,'');
});
