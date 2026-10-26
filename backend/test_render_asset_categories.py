import unittest
from unittest.mock import Mock

from rendering.database import RenderDatabase
from rendering.service import _role_for_category


class RenderAssetCategoryTests(unittest.TestCase):
    def setUp(self):
        self.database = RenderDatabase.__new__(RenderDatabase)
        self.records = [
            {'id': str(i), 'category': category, 'name': category, 'updatedAt': '2026-10-26'}
            for i, category in enumerate(('门扇', '款式', '门扇款式', '包套', '门套', '门套款式', '纹理', '拉手'))
        ]
        self.database.assets = Mock()
        self.database.assets.load.return_value = self.records

    def test_panel_alias_filter_preserves_old_records(self):
        for category in ('门扇', '款式', '门扇款式'):
            self.assertEqual([item['id'] for item in self.database.list_assets(category)], ['0', '1', '2'])
        self.database.assets.update.assert_not_called()

    def test_trim_alias_filter_includes_legacy_wraps(self):
        for category in ('包套', '门套', '门套款式'):
            self.assertEqual([item['id'] for item in self.database.list_assets(category)], ['3', '4', '5'])

    def test_all_view_keeps_retired_categories_and_pagination(self):
        self.assertEqual(len(self.database.list_assets()), 8)
        self.assertEqual([item['id'] for item in self.database.list_assets(limit=2, offset=2)], ['2', '3'])
        self.assertEqual(self.database.list_assets(category='纹理')[0]['id'], '6')

    def test_search_accepts_canonical_label_for_old_assets(self):
        self.assertEqual([item['id'] for item in self.database.list_assets(q='门套款式')], ['3', '4', '5'])

    def test_service_understands_new_and_old_role_labels(self):
        for category in ('门扇', '款式', '门扇款式'):
            self.assertEqual(_role_for_category(category), 'panel')
        for category in ('包套', '门套', '门套款式'):
            self.assertEqual(_role_for_category(category), 'trim')
        for category in ('拉手', '合页', '花件'):
            self.assertEqual(_role_for_category(category), 'hardware')


if __name__ == '__main__':
    unittest.main()
