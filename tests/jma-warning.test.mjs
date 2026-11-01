import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const start = html.indexOf('// BEGIN_JMA_WARNING_PARSER');
const end = html.indexOf('// END_JMA_WARNING_PARSER');
assert.ok(start >= 0 && end > start);
const parse = vm.runInNewContext(html.slice(start, end) + '\nparseBiratoriWarnings');
const report = kinds => ({
  dataTypeCode: 'VPWW61',
  reportDatetime: '2026-11-01T16:02:00+09:00',
  warning: {class20Items:[{areaCode:'0160200',kinds}]}
});

test('平取町の発表中のみ読み、解除は含めない', () => {
  const out = parse([report([{code:'26',status:'発表'},{code:'21',status:'継続'},{code:'14',status:'解除'}])]);
  assert.equal(out.uncertain, false);
  assert.deepEqual(Array.from(out.items, x=>x.name).sort(), ['乾燥注意報','着雪注意報'].sort());
});
test('警報から注意報への切替を発表中として扱い、重大な警報を先に表示する', () => {
  const out = parse([report([{code:'10',status:'警報から注意報'},{code:'43',status:'発表'}])]);
  assert.deepEqual(Array.from(out.items, x=>x.name), ['レベル4大雨危険警報','レベル2大雨注意報']);
});
test('発表なしと未知の状態を区別する', () => {
  assert.equal(parse([report([{status:'発表警報・注意報はなし'}])]).uncertain, false);
  assert.equal(parse([report([{code:'15',status:'未知の状態'}])]).uncertain, true);
  assert.equal(parse([report([{code:'99',status:'発表'}])]).uncertain, true);
  assert.equal(parse([report([])]).uncertain, true);
});
test('他地域だけの情報を発表なしにしない', () => {
  assert.throws(()=>parse([{dataTypeCode:'VPWW61',reportDatetime:'2026-11-01T16:02:00+09:00',warning:{class20Items:[{areaCode:'0160100',kinds:[{status:'発表警報・注意報はなし'}]}]}}]));
});
test('他の報に不明な部分がある場合は明示する', () => {
  const out = parse([report([{code:'26',status:'発表'}]), {dataTypeCode:'VPWW55',reportDatetime:'2026-11-01T16:02:00+09:00',warning:{class20Items:[]}}]);
  assert.equal(out.items[0].name,'着雪注意報');
  assert.equal(out.uncertain,true);
});
