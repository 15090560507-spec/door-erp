"""Loading contracts using temporary fulfillment data only."""
import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from auth import get_current_user
import fulfillment_routes
from fulfillment_database import FulfillmentDatabase
from test_bom_generation import create_door, BomGenerationTest


class ProductionLoadingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = FulfillmentDatabase(os.path.join(self.temp.name, 'fulfillment.db'), os.path.join(self.temp.name, 'files'))
        self.door_id = create_door(self.db, BomGenerationTest.base_params())
        self.order_id = self.db.get_door_unit(self.door_id)['order_id']

    def tearDown(self):
        self.temp.cleanup()

    def test_detail_connections_are_bounded_independent_of_work_count(self):
        with self.db.transaction() as conn:
            package_id = conn.execute('SELECT id FROM fulfillment_technical_packages WHERE door_unit_id=?', (self.door_id,)).fetchone()[0]
            for i in range(30):
                conn.execute("INSERT INTO fulfillment_work_packages(technical_package_id,door_unit_id,name,updated_at) VALUES (?,?,?,'now')", (package_id, self.door_id, f'work-{i}'))
            work_ids = [row[0] for row in conn.execute('SELECT id FROM fulfillment_work_packages WHERE technical_package_id=? ORDER BY id', (package_id,))]
            conn.execute("INSERT INTO fulfillment_work_package_dependencies(successor_id, predecessor_id, created_at) VALUES (?,?,'now')", (work_ids[-1], work_ids[0]))
        with patch.object(self.db, '_connect', wraps=self.db._connect) as connect, patch.object(self.db, 'fetch_all', wraps=self.db.fetch_all) as reads:
            start = time.perf_counter()
            detail = self.db.get_door_unit(self.door_id)
            elapsed = (time.perf_counter() - start) * 1000
            print(f'detail benchmark: connections={connect.call_count}, elapsed_ms={elapsed:.2f}')
        self.assertGreaterEqual(len(detail['technical_package']['work_packages']), 30)
        self.assertLessEqual(connect.call_count, 4)
        self.assertTrue(all('predecessor_ids' in w for w in detail['technical_package']['work_packages']))
        self.assertEqual(next(w for w in detail['technical_package']['work_packages'] if w['id'] == work_ids[-1])['predecessor_ids'], [work_ids[0]])
        self.assertEqual(sum('fulfillment_work_package_dependencies' in str(call.args[0]) for call in reads.call_args_list), 1)

    def test_scoped_read_connection_is_closed_and_reset_on_failure(self):
        with self.assertRaises(ValueError):
            with self.db.read_snapshot() as conn:
                self.assertIsNotNone(self.db.fetch_one('SELECT 1 AS value'))
                raise ValueError('test')
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute('SELECT 1')
        self.assertEqual(self.db.fetch_one('SELECT 2 AS value')['value'], 2)

    def test_order_list_does_not_transfer_drawing_snapshots(self):
        with self.db.transaction() as conn:
            conn.execute("UPDATE fulfillment_orders SET task_snapshot_json=? WHERE id=?", ('{"large_image":"' + 'x' * 100000 + '"}', self.order_id))
        rows = self.db.list_orders()
        self.assertEqual(len(rows), 1)
        self.assertNotIn('task_snapshot_json', rows[0])
        self.assertEqual(rows[0]['id'], self.order_id)
        self.assertEqual(len(self.db.get_order(self.order_id)['task_snapshot']['large_image']), 100000)

    def test_combined_selection_omits_snapshot_but_preserves_default_contract(self):
        app = FastAPI()
        app.include_router(fulfillment_routes.router)
        app.dependency_overrides[get_current_user] = lambda: {'uid': 'test', 'role': '录入员'}
        with patch.object(fulfillment_routes, 'fulfillment_db', self.db), patch.object(fulfillment_routes, 'sales_order_repository', None):
            client = TestClient(app)
            legacy = client.get(f'/api/fulfillment/orders/{self.order_id}').json()
            self.assertIn('task_snapshot', legacy['order'])
            selection = client.get(f'/api/fulfillment/orders/{self.order_id}?include_first_door=true').json()
            self.assertEqual(selection['door_unit']['id'], self.door_id)
            self.assertNotIn('task_snapshot', selection['order'])
            self.assertEqual(client.get('/api/fulfillment/orders/999999?include_first_door=true').status_code, 404)

    def test_dashboard_can_skip_duplicate_pending_scan(self):
        app = FastAPI()
        app.include_router(fulfillment_routes.router)
        app.dependency_overrides[get_current_user] = lambda: {'uid': 'test'}
        with patch.object(fulfillment_routes, 'fulfillment_db', self.db), patch.object(fulfillment_routes, 'pending_release_tasks', return_value=[]) as pending:
            client = TestClient(app)
            self.assertEqual(client.get('/api/fulfillment/dashboard?include_pending=false').status_code, 200)
            pending.assert_not_called()
            self.assertEqual(client.get('/api/fulfillment/dashboard').status_code, 200)
            pending.assert_called_once()
