import importlib.util
from pathlib import Path
import unittest
import urllib.error

spec = importlib.util.spec_from_file_location('feeds', Path(__file__).resolve().parents[1] / 'scripts/update-widget-feeds.py')
feeds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feeds)
NOW = '2026-10-21T14:00:00+00:00'
URL = 'https://example.com/feed/'


class FeedTests(unittest.TestCase):
    def test_valorant_timeout_retries_official_rss_endpoint(self):
        calls = []
        def fetch(url):
            calls.append(url)
            if url.endswith('/feed/'):
                raise urllib.error.URLError(TimeoutError('timed out'))
            return b'<rss><channel><item><title>New article</title><link>https://valorantnews.jp/archives/1</link></item></channel></rss>'
        result = feeds.collect_feed(feeds.VALORANT_FEED, {}, NOW, fetch)
        self.assertEqual(calls, list(feeds.VALORANT_FEED_ROUTES))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['items'][0]['title'], 'New article')
        self.assertEqual(result['generatedAt'], NOW)

    def test_valorant_invalid_retry_keeps_cache_and_timestamp(self):
        for body in (b'<html>Maintenance</html>', b'<rss><channel/></rss>', b'broken XML'):
            def fetch(url):
                if url.endswith('/feed/'):
                    raise urllib.error.URLError(TimeoutError('timed out'))
                return body
            previous = {'items': [{'title': 'old'}], 'generatedAt': '2026-10-20T00:00:00Z'}
            result = feeds.collect_feed(feeds.VALORANT_FEED, previous, NOW, fetch)
            self.assertEqual(result['status'], 'error')
            self.assertEqual(result['error'], 'timeout')
            self.assertEqual(result['items'], previous['items'])
            self.assertEqual(result['generatedAt'], previous['generatedAt'])

    def test_rss2_dates_categories_and_safe_title(self):
        xml = b'''<rss><channel><item><title><![CDATA[<b>A &amp; B</b><script>bad()</script>]]></title><link>https://example.com/1</link><pubDate>Wed, 21 Oct 2026 22:30:00 +0900</pubDate><category>news</category></item></channel></rss>'''
        item = feeds.parse_feed(xml, URL)[0]
        self.assertEqual(item['title'], 'A & B')
        self.assertEqual(item['pubDate'], '2026-10-21T13:30:00+00:00')
        self.assertEqual(item['categories'], ['news'])

    def test_rdf_namespace(self):
        xml = b'''<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/"><item><title>Travel</title><link>https://example.com/1</link><dc:date>2026-10-21T22:00:00+09:00</dc:date></item></rdf:RDF>'''
        self.assertEqual(feeds.parse_feed(xml, URL)[0]['pubDate'], '2026-10-21T13:00:00+00:00')

    def test_atom(self):
        xml = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>News</title><link rel="self" href="/api/1"/><link rel="alternate" href="/1"/><updated>2026-10-21T13:00:00Z</updated><category term="news"/></entry></feed>'''
        self.assertEqual(feeds.parse_feed(xml, URL)[0]['link'], 'https://example.com/1')

    def test_undated_articles_kept_without_invented_date(self):
        xml = b'<rss><channel><item><title>Satire</title><link>https://kyoko-np.net/2026101501.html</link></item></channel></rss>'
        self.assertEqual(feeds.parse_feed(xml, URL)[0]['pubDate'], '')

    def test_missing_and_unsafe_links_rejected(self):
        xml = b'<rss><channel><item><title>A</title></item><item><title>B</title><link>javascript:alert(1)</link></item></channel></rss>'
        with self.assertRaises(ValueError):
            feeds.parse_feed(xml, URL)

    def test_maintenance_preserves_cache_and_success_timestamp(self):
        previous = {'generatedAt': '2026-10-20T00:00:00+00:00', 'items': [{'title': 'old'}]}
        result = feeds.collect_feed(URL, previous, NOW, lambda _: 'ただいまメンテナンス中です。'.encode())
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error'], 'maintenance')
        self.assertEqual(result['generatedAt'], previous['generatedAt'])
        self.assertEqual(result['items'], previous['items'])
        self.assertEqual(result['checkedAt'], NOW)

    def test_http_error_does_not_become_empty_success(self):
        def denied(_):
            raise urllib.error.HTTPError(URL, 403, 'Forbidden', {}, None)
        result = feeds.collect_feed(URL, {}, NOW, denied)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error'], 'HTTP 403')
        self.assertIsNone(result['generatedAt'])

    def test_bear_date_and_notice_failure(self):
        result = feeds.collect_notice('bear', {}, NOW, lambda _: '<p>更新日：2026年10月06日</p>'.encode())
        self.assertEqual(result['latest'], '2026-10-06')
        self.assertEqual(result['status'], 'ok')
        failed = feeds.collect_notice('bear', result, NOW, lambda _: b'<p>maintenance</p>')
        self.assertEqual(failed['status'], 'error')
        self.assertEqual(failed['latest'], '2026-10-06')

    def test_sources_match_existing_settings(self):
        doc = (Path(__file__).resolve().parents[1] / 'index.html').read_text()
        urls = feeds.configured_feeds(doc)
        self.assertEqual(len(urls), 19)
        self.assertIn('https://kyoko-np.net/index.xml', urls)
        self.assertNotIn('https://sasaru.media/category/index.html?id=gourmet', urls)

    def test_goguynet_backup_filters_publisher_date_and_index_pages(self):
        def item(title, publisher, date='Wed, 21 Oct 2026 12:00:00 GMT', key='A'):
            return f'<item><title>{title}</title><link>https://news.google.com/rss/articles/{key}</link><pubDate>{date}</pubDate><source url="https://{publisher}">News</source></item>'
        body = ('<rss><channel>' + item('【苫小牧市】新店 - 地域ニュースサイト号外NET', 'tomakomai.goguynet.jp')
                + item('イベント', 'tomakomai.goguynet.jp', key='B')
                + item('【苫小牧市】別サイト', 'example.com', key='C')
                + item('【苫小牧市】古い', 'tomakomai.goguynet.jp', 'Wed, 01 Oct 2025 12:00:00 GMT', 'D')
                + '<item><title>Missing source</title></item></channel></rss>').encode()
        def fetch(url):
            if url == feeds.GOGUYNET_FEED:
                raise urllib.error.HTTPError(url, 503, 'Unavailable', {}, None)
            return body
        result = feeds.collect_feed(feeds.GOGUYNET_FEED, {}, NOW, fetch)
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(result['fallback'])
        self.assertEqual(result['primaryError'], 'HTTP 503')
        self.assertEqual([i['title'] for i in result['items']], ['【苫小牧市】新店'])

    def test_both_feed_paths_failed_preserve_previous_success(self):
        def fetch(url):
            raise urllib.error.HTTPError(url, 503, 'Unavailable', {}, None)
        previous = {'items': [{'title': 'old'}], 'generatedAt': '2026-10-20T00:00:00Z'}
        result = feeds.collect_feed(feeds.GOGUYNET_FEED, previous, NOW, fetch)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['items'], previous['items'])
        self.assertEqual(result['generatedAt'], previous['generatedAt'])

    def test_okuyami_fallback_and_badge_ignore_daily_date(self):
        body = '<h1>平取町の本日のお悔やみ欄・訃報一覧</h1><time>2026-10-21</time><article class="obituary-item"><h4>架空の見出し</h4></article>'
        def fetch(url):
            if url == feeds.NOTICE_URLS['okuyami']:
                raise urllib.error.HTTPError(url, 403, 'Forbidden', {}, None)
            return body.encode()
        record = feeds.collect_notice('okuyami', {}, NOW, fetch)
        self.assertEqual(record['status'], 'ok')
        self.assertEqual(record['sourceUrl'], feeds.OKUYAMI_BACKUP)
        self.assertNotIn('架空', record['latest'])
        self.assertEqual(record['latest'], feeds.parse_okuyami_backup(body.replace('2026-10-21', '2026-10-22')))
        self.assertNotEqual(record['latest'], feeds.parse_okuyami_backup(body.replace('架空の見出し', '新しい架空の見出し')))
        with self.assertRaises(ValueError):
            feeds.parse_okuyami_backup(body.replace('平取町', '別の町'))


if __name__ == '__main__':
    unittest.main()
