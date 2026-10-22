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


if __name__ == '__main__':
    unittest.main()
