import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError
from quote_database import QuoteDatabaseManager
from quote_models import QuoteCreate
from quote_excel import _quote_quantity, _quote_amount
import quote_routes


def payload(factor=.7):
    return {'customerName': 'Dual trim', 'quoteDate': '2026-10-26', 'doorGroups': [{
        'taskId': 'exact-task', 'doorQuantity': 2, 'extraTrimFactor': factor, 'items': [
            {'productName': 'Door', 'pricingRole': 'mainDoor', 'category': '门类组合',
             'width': 1300, 'height': 2150, 'unit': 'm2', 'unitPrice': 1480},
            {'productName': 'Inner trim', 'pricingRole': 'extraTrim', 'category': '附加门套',
             'quantity': .52, 'unit': 'm2', 'unitPrice': 1036},
        ]}]}


class DualTrimQuoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db = QuoteDatabaseManager(str(root / 'quotes.json'), str(root / 'backups'))

    def tearDown(self):
        self.temp.cleanup()

    def test_factor_and_roles_survive_request_save_reload_update(self):
        data = QuoteCreate.model_validate(payload()).model_dump()
        quote = self.db.create(data)
        stored = self.db.get_by_id(quote['id'])
        self.assertEqual(stored['doorGroups'][0]['extraTrimFactor'], .7)
        self.assertEqual([item['pricingRole'] for item in stored['items']], ['mainDoor', 'extraTrim'])
        updated = self.db.update(quote['id'], QuoteCreate.model_validate(payload(.8)).model_dump())
        self.assertEqual(updated['doorGroups'][0]['extraTrimFactor'], .8)
        self.assertEqual(updated['doorGroups'][0]['doorQuantity'], 2)

    def test_legacy_factor_default_and_zero_remain_distinct(self):
        data = payload()
        del data['doorGroups'][0]['extraTrimFactor']
        self.assertEqual(self.db.create(data)['doorGroups'][0]['extraTrimFactor'], .7)
        self.assertEqual(self.db.create(payload(0))['doorGroups'][0]['extraTrimFactor'], 0)

    def test_invalid_factors_rejected_by_model_and_storage(self):
        for value in (-.1, float('nan'), float('inf'), None, 'invalid'):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    QuoteCreate.model_validate(payload(value))
                with self.assertRaises(ValueError):
                    self.db.create(payload(value))

    def test_export_preserves_main_rectangle_and_extra_net_quantity(self):
        quote = self.db.create(payload())
        main, extra = quote['items']
        self.assertEqual(_quote_quantity(main), 2.795)
        self.assertEqual(_quote_quantity(extra), .52)
        self.assertEqual(_quote_amount(extra), 539)

    def test_task_lookup_uses_exact_id_and_preserves_latest_saved_prices(self):
        first = self.db.create(payload())
        second = self.db.create(payload(.8))
        other = payload()
        other['doorGroups'][0]['taskId'] = 'exact-task-other'
        self.db.create(other)
        with patch.object(quote_routes, 'quote_db', self.db):
            result = quote_routes.latest_quote_for_task('exact-task', current_user={})
            self.assertEqual(result['quote']['id'], second['id'])
            self.assertEqual(result['quote']['items'][1]['unitPrice'], 1036)
            self.assertEqual(result['quote']['doorGroups'][0]['extraTrimFactor'], .8)
            self.assertIsNone(quote_routes.latest_quote_for_task('missing', current_user={})['quote'])
        self.assertNotEqual(first['id'], second['id'])


if __name__ == '__main__':
    unittest.main()
