"""Collect public RSS and update badges without browser-side proxy services."""
import concurrent.futures
import email.utils
import html
import hashlib
import http.client
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/widget-feeds.json'
MAX_BYTES = 5_000_000
NOTICE_URLS = {
    'bear': 'https://www.town.biratori.hokkaido.jp/soshikikarasagasu/chominka/seikatsukankyokakari/1/1/2/323.html',
    'okuyami': 'https://okuyami-media.com/category/hokkaido-region/hokkaido-pref/%e5%b9%b3%e5%8f%96%e7%94%ba/',
}
OKUYAMI_BACKUP = 'https://zenkoku-okuyami.com/obituary/hokkaido/biratoricho/'
GOGUYNET_FEED = 'https://tomakomai.goguynet.jp/feed/'


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def plain(value):
    parser = TextParser()
    parser.feed(value)
    return re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()


def local_name(tag):
    return tag.rsplit('}', 1)[-1]


def date_string(value):
    if not value:
        return ''
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        try:
            date = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return ''
    if date.tzinfo is None:
        return ''  # Do not guess a publisher's timezone.
    return date.astimezone(timezone.utc).isoformat()


def parse_feed(body, source):
    root = ET.fromstring(body)
    if local_name(root.tag).lower() not in ('rss', 'rdf', 'feed'):
        raise ValueError('not_rss')
    items = []
    seen = set()
    for node in root.iter():
        if local_name(node.tag) not in ('item', 'entry'):
            continue
        def text(*names):
            for name in names:
                for child in node:
                    if local_name(child.tag) == name:
                        return ''.join(child.itertext()).strip()
            return ''
        title = plain(text('title'))
        link = text('link')
        if not link:
            link = next((c.get('href', '') for c in node if local_name(c.tag) == 'link' and c.get('rel', 'alternate') == 'alternate'), '')
        if not link:
            continue
        link = urllib.parse.urljoin(source, html.unescape(link))
        if not title or urllib.parse.urlsplit(link).scheme not in ('https', 'http') or link in seen:
            continue
        seen.add(link)
        items.append({
            'title': title, 'link': link,
            'pubDate': date_string(text('pubDate', 'date', 'published', 'updated')),
            'categories': [plain(''.join(c.itertext()) or c.get('term', '')) for c in node if local_name(c.tag) in ('category', 'subject')],
        })
    if not items and any(local_name(n.tag) in ('item', 'entry') for n in root.iter()):
        raise ValueError('invalid_items')
    return items[:100]


def configured_feeds(document):
    match = re.search(r'const urls = \{([\s\S]*?)\n\};', document)
    if not match:
        raise ValueError('news_sources_missing')
    urls = list(dict.fromkeys(re.findall(r'"(https?[^"\n]+)"', match[1])))
    # These sources already have dedicated HTML collectors in the same workflow.
    return [url for url in urls if urllib.parse.urlsplit(url).hostname not in ('sasaru.media', 'www.walkerplus.com')
            and urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get('q') != ['site:domingo.ne.jp']]


def fetch_bytes(url):
    encoded = urllib.parse.quote(url, safe=':/?&=%')
    request = urllib.request.Request(encoded, headers={'User-Agent': 'BiratoriWidget/1.0 (public RSS reader)', 'Accept': 'application/rss+xml, application/xml, text/html;q=0.8, */*;q=0.5'})
    with urllib.request.urlopen(request, timeout=25) as response:
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('response_too_large')
        return data


def failure_reason(error):
    if isinstance(error, urllib.error.HTTPError):
        return 'HTTP ' + str(error.code)
    if isinstance(error, (TimeoutError, socket.timeout)):
        return 'timeout'
    if isinstance(error, http.client.IncompleteRead):
        return 'incomplete_response'
    if isinstance(error, ET.ParseError):
        return 'invalid_rss'
    if isinstance(error, ValueError):
        return str(error) if str(error) in ('not_rss', 'invalid_items', 'maintenance', 'response_too_large', 'update_date_missing', 'entry_title_missing') else 'invalid_response'
    return 'network_error'


def google_news_backup(host, checked_at, fetch=fetch_bytes):
    url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode({
        'q': 'site:' + host + ' when:14d', 'hl': 'ja', 'gl': 'JP', 'ceid': 'JP:ja'})
    body = fetch(url)
    root = ET.fromstring(body)
    # Check the publisher supplied by the RSS, not just a matching word in a title.
    allowed = {node.findtext('link') for node in root.findall('.//item')
               if node.find('source') is not None
               and urllib.parse.urlsplit(node.find('source').get('url', '')).hostname == host}
    now = datetime.fromisoformat(checked_at)
    items = []
    for item in parse_feed(body, url):
        link = urllib.parse.urlsplit(item['link'])
        date = date_string(item['pubDate'])
        if item['link'] not in allowed or link.hostname != 'news.google.com' or not link.path.startswith('/rss/articles/') or not date:
            continue
        age = (now - datetime.fromisoformat(date)).total_seconds()
        if not 0 <= age <= 14 * 86400 or not item['title'].startswith('【苫小牧市'):
            continue
        item['title'] = re.sub(r'\s+-\s+地域ニュースサイト号外NET$', '', item['title'])
        items.append(item)
    if not items:
        raise ValueError('backup_articles_missing')
    return items, url


def collect_feed(url, previous, checked_at, fetch=fetch_bytes):
    try:
        body = fetch(url)
        if 'メンテナンス' in body[:2000].decode('utf-8', errors='replace'):
            raise ValueError('maintenance')
        items = parse_feed(body, url)
        return {'status': 'ok', 'generatedAt': checked_at, 'checkedAt': checked_at, 'items': items}
    except (OSError, ValueError, ET.ParseError, http.client.HTTPException) as error:
        if url == GOGUYNET_FEED:
            try:
                items, backup_url = google_news_backup('tomakomai.goguynet.jp', checked_at, fetch)
                return {'status': 'ok', 'generatedAt': checked_at, 'checkedAt': checked_at, 'items': items,
                        'fallback': True, 'source': '号外NET苫小牧（Googleニュース経由・直近14日）',
                        'sourceUrl': backup_url, 'primaryError': failure_reason(error)}
            except (OSError, ValueError, ET.ParseError, http.client.HTTPException):
                pass
        # Keep the last successful timestamp; a failed check must not look fresh.
        return {'status': 'error', 'generatedAt': previous.get('generatedAt'), 'checkedAt': checked_at,
                'error': failure_reason(error), 'items': previous.get('items', [])}


def parse_okuyami_backup(body):
    title = re.search(r'<h1\b[^>]*>([\s\S]*?)</h1>', body, re.I)
    if not title or '平取町の本日のお悔やみ' not in plain(title[1]):
        raise ValueError('wrong_municipality')
    # Fingerprint only obituary entries. The daily check date and ads must not
    # create a new-information badge. Store no names or funeral details.
    cards = re.findall(r'<article\b[^>]*class=["\'][^"\']*\bobituary-item\b[^"\']*["\'][^>]*>([\s\S]*?)</article>', body, re.I)
    entries = sorted(set(plain(card) for card in cards))
    if not entries and '本日の掲載はありません' not in plain(body):
        raise ValueError('entry_title_missing')
    return 'zenkoku-okuyami:' + hashlib.sha256('\n'.join(entries).encode()).hexdigest()


def collect_notice(kind, previous, checked_at, fetch=fetch_bytes):
    try:
        body = fetch(NOTICE_URLS[kind]).decode('utf-8', errors='replace')
        if kind == 'bear':
            match = re.search(r'更新日[：:]\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日', plain(body))
            if not match:
                raise ValueError('update_date_missing')
            latest = datetime(*map(int, match.groups())).strftime('%Y-%m-%d')
        else:
            match = re.search(r'<h[1-6]\b[^>]*class=["\'][^"\']*\bentry-title\b[^"\']*["\'][^>]*>([\s\S]*?)</h[1-6]>', body, re.I)
            latest = plain(match[1]) if match else ''
            if not latest:
                raise ValueError('entry_title_missing')
        return {'status': 'ok', 'latest': latest, 'generatedAt': checked_at, 'checkedAt': checked_at}
    except (OSError, ValueError, http.client.HTTPException) as error:
        if kind == 'okuyami':
            try:
                latest = parse_okuyami_backup(fetch(OKUYAMI_BACKUP).decode('utf-8', errors='replace'))
                return {'status': 'ok', 'latest': latest, 'generatedAt': checked_at, 'checkedAt': checked_at,
                        'fallback': True, 'source': '全国お悔やみ欄（平取町）', 'sourceUrl': OKUYAMI_BACKUP,
                        'primaryError': failure_reason(error)}
            except (OSError, ValueError, http.client.HTTPException):
                pass
        return {**previous, 'status': 'error', 'checkedAt': checked_at, 'error': failure_reason(error)}


def main():
    urls = configured_feeds((ROOT / 'index.html').read_text())
    previous = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    now = datetime.now(timezone.utc).isoformat()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = {url: pool.submit(collect_feed, url, previous.get('feeds', {}).get(url, {}), now) for url in urls}
        notices = {key: pool.submit(collect_notice, key, previous.get('notices', {}).get(key, {}), now) for key in NOTICE_URLS}
        feeds = {url: task.result() for url, task in futures.items()}
        notices = {key: task.result() for key, task in notices.items()}
    payload = {'version': 1, 'generatedAt': now, 'feeds': feeds, 'notices': notices}
    OUTPUT.parent.mkdir(exist_ok=True)
    temporary = OUTPUT.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(OUTPUT)
    for url, record in feeds.items():
        print(f"{record['status']}: {url}: {len(record['items'])} items" + (f" ({record['error']})" if record.get('error') else '')
              + (f" (backup: {record['source']}; primary: {record['primaryError']})" if record.get('fallback') else ''))
    for key, record in notices.items():
        print(f"{record['status']}: {key}" + (f" ({record['error']})" if record.get('error') else '')
              + (f" (backup: {record['source']}; primary: {record['primaryError']})" if record.get('fallback') else ''))
    failures = sum(record['status'] != 'ok' for record in feeds.values())
    print(f'RSS sources: {len(feeds) - failures}/{len(feeds)} successful. Failed sources are reported in the widget.')
    if failures == len(feeds):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
