import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from quote_database import QuoteDatabaseManager


class QuoteHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'quotes.json'
        records = [
            {
                'id': index,
                'customerName': 'oldest' if index == 1 else f'Customer {index}',
                'projectName': 'Project',
                'quoteDate': '2026-10-08' if index == 1 else '2026-10-09',
                'items': [{'productName': 'Primary door', 'width': 900, 'height': 2100}],
                'doorGroups': [
                    {'items': [{'productName': 'Primary door', 'width': 900, 'height': 2100}]},
                    {'items': [{'productName': 'Secondary special' if index == 1 else 'Secondary',
                                'width': 1234 if index == 1 else 1000, 'height': 2345}]},
                ],
            }
            for index in range(1, 122)
        ]
        self.path.write_text(json.dumps(records), encoding='utf-8')
        self.db = QuoteDatabaseManager(str(self.path), str(Path(self.temp.name) / 'backups'))

    def test_all_records_are_accessible_in_pages(self):
        pages = [self.db.get_page(offset=offset) for offset in (0, 50, 100)]
        self.assertEqual([len(page['quotes']) for page in pages], [50, 50, 21])
        self.assertEqual([page['total'] for page in pages], [121] * 3)
        ids = [quote['id'] for page in pages for quote in page['quotes']]
        self.assertEqual(ids, list(range(121, 0, -1)))
        self.assertNotIn('items', pages[0]['quotes'][0])
        self.assertEqual(pages[0]['quotes'][0]['doorCount'], 2)
        self.assertEqual(self.db.get_page(offset=200)['quotes'], [])

    def test_search_filters_all_records_and_all_groups_before_paging(self):
        for query in (' oldest ', 'SECONDARY SPECIAL', '1234 x 2345', '1234'):
            with self.subTest(query=query):
                page = self.db.get_page(q=query)
                self.assertEqual(page['total'], 1)
                self.assertEqual(page['quotes'][0]['id'], 1)
        self.assertEqual(self.db.get_page(quote_date='2026-10-08')['total'], 1)
        self.assertEqual(self.db.get_page(q='oldest', quote_date='2026-10-09')['total'], 0)

    def test_legacy_items_search_and_summary(self):
        records = json.loads(self.path.read_text(encoding='utf-8'))
        records[0].pop('doorGroups')
        records[0]['items'][0]['productName'] = 'Legacy door'
        self.path.write_text(json.dumps(records), encoding='utf-8')
        self.assertEqual(self.db.get_page(q='legacy')['quotes'][0]['doorSummary'], 'Legacy door')
        self.assertEqual(len(self.db.get_all(limit=3)), 3)

    def test_float_dimensions_match_displayed_integer_size(self):
        records = json.loads(self.path.read_text(encoding='utf-8'))
        records[0]['doorGroups'][1]['items'][0].update(width=1234.0, height=2345.0)
        self.path.write_text(json.dumps(records), encoding='utf-8')
        self.assertEqual(self.db.get_page(q='1234 x 2345')['quotes'][0]['id'], 1)

    def test_unreadable_storage_is_not_treated_as_empty_or_overwritten(self):
        self.path.write_text('{broken-json', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.db.get_page()
        with self.assertRaises(ValueError):
            self.db.create({'customerName': 'New', 'quoteDate': '2026-10-09',
                            'items': [{'productName': 'Door'}]})
        self.assertEqual(self.path.read_text(encoding='utf-8'), '{broken-json')

    def test_create_update_do_not_trim_old_quotes(self):
        data = {'customerName': 'New', 'quoteDate': '2026-10-09',
                'items': [{'productName': 'Door'}]}
        quote = self.db.create(data)
        self.db.update(quote['id'], {**data, 'customerName': 'Updated'})
        self.assertEqual(self.db.get_page()['total'], 122)
        self.assertEqual(self.db.get_by_id(1)['customerName'], 'oldest')
        self.db.delete(quote['id'])
        self.assertEqual(self.db.get_page()['total'], 121)

    def test_invalid_pagination_is_rejected(self):
        for kwargs in ({'limit': 0}, {'limit': 201}, {'offset': -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.db.get_page(**kwargs)

    def test_route_pagination_and_validation(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from auth import get_current_user
        from quote_routes import quote_router
        app = FastAPI()
        app.include_router(quote_router)
        app.dependency_overrides[get_current_user] = lambda: {'uid': 'test'}
        with patch('quote_routes.quote_db', self.db), TestClient(app) as client:
            response = client.get('/api/quotes', params={'offset': 100})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['total'], 121)
            self.assertEqual(len(response.json()['quotes']), 21)
            response = client.get('/api/quotes', params={'q': 'oldest', 'quoteDate': '2026-10-08'})
            self.assertEqual(response.json()['quotes'][0]['id'], 1)
            self.assertEqual(client.get('/api/quotes?offset=-1').status_code, 422)
            self.assertEqual(client.get('/api/quotes?limit=201').status_code, 422)


if __name__ == '__main__':
    unittest.main()
