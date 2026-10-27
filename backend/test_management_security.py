"""Business permission boundaries and immutable payroll/approval contracts."""
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import auth
import bom_routes
import business_access_routes
import fulfillment_routes
import inventory_routes
import operations_routes
import sales_order_routes
import test_bom_generation as bom_fixtures
from business_permissions import ALL_BUSINESS_PERMISSIONS, business_permissions
from database import UserDatabaseManager
from fulfillment_database import FulfillmentDatabase
from fulfillment_models import ShipmentCreate
from management_access import require_management_access, route_permissions


class ManagementSecurityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='management-security-')
        self.addCleanup(self.temp.cleanup)
        self.db = FulfillmentDatabase(os.path.join(self.temp.name, 'db.sqlite'), os.path.join(self.temp.name, 'files'))
        self.users = UserDatabaseManager(os.path.join(self.temp.name, 'users.json'), os.path.join(self.temp.name, 'backups'))
        self.users.add_or_update_user('E', 'test-secret', '录入员', '普通录入')
        self.user = {'uid': 'A', 'name': '销售小A', 'role': '录入员'}
        self.app = FastAPI()
        for module in (operations_routes, fulfillment_routes, business_access_routes, inventory_routes, bom_routes, sales_order_routes):
            self.app.include_router(module.router)
        self.app.dependency_overrides[auth.get_current_user] = lambda: self.user
        for module in (operations_routes, fulfillment_routes):
            p = patch.object(module, 'fulfillment_db', self.db)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(business_access_routes, 'user_db', self.users)
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(fulfillment_routes, 'sales_order_repository', None)
        p.start()
        self.addCleanup(p.stop)
        self.client = TestClient(self.app)

    def account(self, *permissions):
        self.user = {'uid': 'E', 'role': '录入员', 'name': '测试账号', 'management_permissions': list(permissions)}

    def payroll(self):
        self.client.post('/api/operations/employees', json={'employee_no': 'E01', 'name': '员工', 'base_salary': 5000}).raise_for_status()
        response = self.client.post('/api/operations/payroll/calculate', json={'month': '2026-10'})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['period']

    def transition(self, period, status, reason='', expected_status=None):
        return self.client.put(f"/api/operations/payroll/{period['id']}/status", json={
            'status': status, 'reason': reason, 'expected_status': expected_status,
        })

    def test_admin_a_and_explicit_overrides(self):
        for user in ({'uid': 'A', 'role': '录入员', 'management_permissions': []}, {'uid': 'root', 'role': '超级管理员'}):
            self.assertEqual(business_permissions(user), ALL_BUSINESS_PERMISSIONS)
        self.assertNotIn('finance.release', business_permissions({'uid': 'E', 'role': '录入员'}))
        self.assertEqual(business_permissions({'uid': 'E', 'role': '录入员', 'management_permissions': []}), set())
        self.assertEqual(business_permissions({'uid': 'E', 'role': 'unknown'}), set())
        self.assertIn('payroll.read', business_permissions({'management_permissions': ['payroll.approve']}))
        self.assertNotIn('payroll.unlock', business_permissions({'management_permissions': ['payroll.approve']}))

    def test_all_business_routes_have_explicit_policies(self):
        for module in (operations_routes, fulfillment_routes, inventory_routes, bom_routes, sales_order_routes):
            for route in module.router.routes:
                self.assertIn(require_management_access, [d.call for d in route.dependant.dependencies], route.path)
                for method in route.methods:
                    self.assertIsNotNone(route_permissions(method, route.path), (method, route.path))
        self.assertIsNone(route_permissions('POST', '/api/operations/new-unreviewed-action'))

    def test_login_is_not_sufficient_for_sensitive_endpoints(self):
        self.user = {'uid': 'E', 'role': '录入员'}
        for method, path, body in (
            ('get', '/api/operations/payroll', None),
            ('post', '/api/operations/employees', {'employee_no': 'E99', 'name': 'X'}),
            ('post', '/api/operations/payroll/calculate', {'month': '2026-10'}),
            ('post', '/api/fulfillment/door-units/1/payments', {'amount': 1}),
            ('post', '/api/fulfillment/door-units/1/shipments', {}),
            ('post', '/api/inventory/adjustments', {}),
        ):
            response = self.client.request(method, path, json=body) if body is not None else self.client.get(path)
            self.assertEqual(response.status_code, 403, (path, response.text))
        self.assertEqual(self.db.fetch_all('SELECT * FROM workforce_employees'), [])

    def test_permission_assignment_is_audited_and_preserves_credentials(self):
        before = self.users.load_all_users()['E']
        response = self.client.put('/api/business-access/E', json={'permissions': ['payroll.approve'], 'reason': '负责审核'})
        self.assertEqual(response.status_code, 200, response.text)
        after = self.users.load_all_users()['E']
        self.assertEqual(after['password'], before['password'])
        self.assertEqual(after['role'], before['role'])
        self.assertEqual(after['permission_audit'][0]['operator_uid'], 'A')
        self.assertNotIn('password', response.json()['users']['E'])
        self.assertNotIn('permission_audit', response.json()['users']['E'])
        self.assertEqual(self.client.get('/api/business-access/E/history').json()['events'][0]['reason'], '负责审核')
        self.users.add_or_update_user('E', 'replacement', '录入员', '改名')
        self.assertEqual(self.users.load_all_users()['E']['management_permissions'], ['payroll.approve'])
        self.assertEqual(len(self.users.load_all_users()['E']['permission_audit']), 1)
        for target, permissions, reason in (('A', [], '不能降权'), ('E', ['invented'], '无效'), ('E', [], ' ')):
            self.assertEqual(self.client.put(f'/api/business-access/{target}', json={'permissions': permissions, 'reason': reason}).status_code, 400)
        self.account('payroll.approve')
        self.assertEqual(self.client.get('/api/business-access').status_code, 403)

    def test_existing_token_uses_current_server_grants(self):
        self.app.dependency_overrides.clear()
        with patch.object(auth, 'user_db', self.users):
            token = auth.create_token('E')
            headers = {'Authorization': f'Bearer {token}'}
            self.assertEqual(self.client.get('/api/operations/payroll', headers=headers).status_code, 403)
            forged_claims = auth.jwt.encode({'sub': 'E', 'permissions': list(ALL_BUSINESS_PERMISSIONS)}, auth.JWT_SECRET, algorithm=auth.JWT_ALGORITHM)
            self.assertEqual(self.client.get('/api/operations/payroll', headers={'Authorization': f'Bearer {forged_claims}'}).status_code, 403)
            self.users.update_management_permissions('E', ['payroll.read'], {'uid': 'A'}, '授予查看')
            self.assertEqual(self.client.get('/api/operations/payroll', headers=headers).status_code, 200)
            self.users.update_management_permissions('E', [], {'uid': 'A'}, '撤销查看')
            self.assertEqual(self.client.get('/api/operations/payroll', headers=headers).status_code, 403)
            self.assertEqual(self.client.get('/api/operations/payroll').status_code, 401)

    def test_salary_is_redacted_for_production_readers(self):
        self.payroll()
        self.account('production.read')
        self.assertNotIn('base_salary', self.client.get('/api/operations/employees').json()['employees'][0])
        self.account('payroll.read')
        self.assertEqual(self.client.get('/api/operations/employees').json()['employees'][0]['base_salary'], 5000)

    def test_payroll_freezes_on_submission_and_reopening_is_reasoned(self):
        period = self.payroll()
        entry = period['entries'][0]
        url = f"/api/operations/payroll/entries/{entry['id']}"
        self.assertEqual(self.client.put(url, json={'allowance': 100}).status_code, 200)
        self.account('payroll.write')
        self.assertEqual(self.transition(period, '待审核').status_code, 200)
        self.assertEqual(self.transition(period, '已审批').status_code, 403)
        self.assertEqual(self.client.put(url, json={'allowance': 999}).status_code, 409)
        self.assertEqual(self.client.post('/api/operations/payroll/calculate', json={'month': '2026-10'}).status_code, 409)
        self.account('payroll.approve')
        approved = self.transition(period, '已审批').json()['period']
        self.assertEqual(approved['approved_by'], 'E')
        self.assertEqual(self.transition(period, '草稿', '试图越权').status_code, 403)
        self.assertEqual(self.transition(period, '已锁定').status_code, 200)
        self.account('payroll.unlock')
        self.assertEqual(self.transition(period, '草稿').status_code, 400)
        self.assertEqual(self.transition(period, '草稿', '核对补贴', '已审批').status_code, 409)
        reopened = self.transition(period, '草稿', '核对补贴', '已锁定')
        self.assertEqual(reopened.status_code, 200, reopened.text)
        data = reopened.json()['period']
        self.assertFalse(data['approved_by'])
        self.assertFalse(data['approved_at'])
        self.assertEqual(data['entries'][0]['allowance'], 100)
        self.assertIn('核对补贴', data['audit_events'][0]['detail'])
        self.assertEqual(data['audit_events'][0]['operator_uid'], 'E')
        self.assertEqual(self.transition(period, '已审批').status_code, 409)

    def test_even_admin_cannot_directly_modify_approved_payroll(self):
        period = self.payroll()
        self.transition(period, '待审核').raise_for_status()
        self.transition(period, '已审批').raise_for_status()
        self.assertEqual(self.client.put(f"/api/operations/payroll/entries/{period['entries'][0]['id']}", json={'bonus': 100}).status_code, 409)
        self.assertEqual(self.client.post('/api/operations/payroll/calculate', json={'month': '2026-10'}).status_code, 409)

    def shipping_door(self):
        door_id = bom_fixtures.create_door(self.db, bom_fixtures.BomGenerationTest.base_params())
        with self.db.transaction() as conn:
            conn.execute("UPDATE fulfillment_door_units SET status='已入库待发货' WHERE id=?", (door_id,))
        return door_id

    def test_arbitrary_approver_cannot_release_and_failure_has_no_side_effect(self):
        door_id = self.shipping_door()
        self.account('production.shipping')
        payload = {'required_payment': 1000, 'authorize_release': True, 'authorization_reason': '欠款发货', 'authorized_by': '老板'}
        result = self.client.post(f'/api/fulfillment/door-units/{door_id}/shipments', json=payload)
        self.assertEqual(result.status_code, 403, result.text)
        self.assertEqual(self.db.fetch_all('SELECT * FROM fulfillment_shipments'), [])
        self.assertEqual(self.db.fetch_all("SELECT * FROM fulfillment_inventory_movements WHERE movement_type='发货出库'"), [])
        self.assertEqual(self.db.fetch_one('SELECT status FROM fulfillment_door_units WHERE id=?', (door_id,))['status'], '已入库待发货')
        self.assertEqual(self.client.post(f'/api/fulfillment/door-units/{door_id}/shipments', json={'required_payment': 1000}).status_code, 409)

    def test_release_requires_explicit_confirmation_and_real_actor(self):
        door_id = self.shipping_door()
        self.account('production.shipping', 'finance.release')
        for payload in ({'authorization_reason': '理由', 'authorized_by': '老板'}, {'authorize_release': True}):
            self.assertEqual(self.client.post(f'/api/fulfillment/door-units/{door_id}/shipments', json=payload).status_code, 400)
        payload = ShipmentCreate(required_payment=1000, authorize_release=True, authorization_reason='约定月末付款', authorized_by='伪造')
        self.db.create_shipment(door_id, payload, self.user, sales_finance={'total_amount': 1000, 'paid_amount': 100, 'unpaid_amount': 900})
        row = self.db.fetch_all('SELECT * FROM fulfillment_shipments')[0]
        self.assertEqual(row['authorized_by'], 'E')
        self.assertEqual(row['authorization_reason'], '约定月末付款')
        event = self.db.fetch_all("SELECT * FROM fulfillment_events WHERE entity_type='shipment'")[0]
        self.assertIn('900.00', event['detail'])
        self.assertEqual(event['operator_uid'], 'E')

    def test_batch_skip_and_supply_status_do_not_bypass_roles(self):
        self.account('production.worker')
        response = self.client.post('/api/fulfillment/door-units/1/work-packages/batch', json={'work_ids': [1], 'action': '跳过', 'remark': '试图绕过主管'})
        self.assertEqual(response.status_code, 403, response.text)
        self.account('production.purchase')
        response = self.client.put('/api/fulfillment/supplies/1', json={'status': '已入库'})
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.db.fetch_all('SELECT * FROM fulfillment_inventory_movements'), [])

    def test_user_managers_share_write_lock_and_password_reset_preserves_grants(self):
        other = UserDatabaseManager(self.users.file_path, self.users.backup_dir)
        self.assertIs(other._permission_lock, self.users._permission_lock)
        self.users.update_management_permissions('E', ['payroll.read'], {'uid': 'A'}, '只读')
        other.reset_password('E', 'new-secret')
        self.assertEqual(other.load_all_users()['E']['management_permissions'], ['payroll.read'])
        self.assertEqual(other.load_all_users()['E']['permission_audit'][0]['reason'], '只读')
        self.assertIsNotNone(other.authenticate('E', 'new-secret'))


if __name__ == '__main__':
    unittest.main()
