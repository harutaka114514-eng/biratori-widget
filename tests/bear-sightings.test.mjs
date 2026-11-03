import { test} from 'node:test';
import assert from 'node:assert/strict';
import { parseBearSightings} from '../scripts/update-bear-sightings.mjs';

const sample = `<!doctype html><html><body>
<h2>平取町のヒグマ出没情報（令和8年度）</h2>
<p>令和8年10月29日現在 </p>
<a href="https://www.google.com/maps/d/viewer?mid=abc123&amp;ll=42.5%2C142.1">クマ出没情報（Googleマイマップ）</a>
<table>
<tr><th>No</th><th>月日</th><th>時間</th><th>場所</th><th>確認</th></tr>
<tr><td>1</td><td>5月11日<br>（月曜日）</td><td>5時00分ごろ</td><td>川向</td><td>職員現場確認、看板設置</td></tr>
<tr><td>2</td><td>10月26日<br>（月曜日）</td><td>20時30分ごろ</td><td>岩知志</td><td>職員による現場確認</td></tr>
<tr><td>3</td><td>2月3日<br>（水曜日）</td><td>早朝</td><td>本町</td><td></td></tr>
</table>
</body></html>`;

test('平取町の出没表を新しい順に読み、年度またぎを翌年にする', () => {
const out = parseBearSightings(sample);
assert.equal(out.fiscalYearLabel, '令和8年度');
assert.equal(out.asOf, '2026-10-29');
assert.equal(out.mapUrl, 'https://www.google.com/maps/d/viewer?mid=abc123&ll=42.5%2C142.1');
assert.deepEqual(out.items.map(x => x.date), ['2027-02-03', '2026-10-26', '2026-05-11']);
assert.equal(out.items[1].place, '岩知志');
assert.equal(out.items[1].time, '20時30分ごろ');
});

test('見出しや行が無いページは失敗として扱う', () => {
assert.throws(() => parseBearSightings('<html><body>ヒグマ出没情報</body></html>'));
assert.throws(() => parseBearSightings('<html><body>関係ないページ</body></html>'));
});
