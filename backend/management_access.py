"""Explicit, fail-closed authorization for management routes."""
import re
from fastapi import Depends, HTTPException, Request
from auth import get_current_user
from business_permissions import ensure_business_permission

ROUTE_POLICIES = {}


def _register(domain, permissions, routes):
    for route in routes.splitlines():
        if route.strip():
            method, path = route.strip().split(' ', 1)
            key = (method, '/api/' + domain + path)
            if key in ROUTE_POLICIES:
                raise RuntimeError('Duplicate management policy: ' + str(key))
            ROUTE_POLICIES[key] = tuple(permissions.split())


_register('fulfillment', 'production.read', '''
GET /dashboard
GET /people
GET /pending-release
GET /orders
GET /orders/{}
GET /door-units/{}
GET /door-units/{}/calculation
GET /door-units/{}/frame-input
''')
_register('fulfillment', 'production.sales production.manager', 'POST /orders/from-task/{}')
_register('fulfillment', 'production.technical production.cutting', '''
POST /door-units/{}/calculation/initialize
PUT /door-units/{}/calculation
POST /door-units/{}/calculation/submit
POST /door-units/{}/calculation/publish
POST /door-units/{}/bom/frame/recalculate
PUT /door-units/{}/technical-package
POST /door-units/{}/technical-package/confirm
''')
_register('fulfillment', 'production.worker production.schedule production.manager production.quality', '''
PUT /work-packages/{}
POST /door-units/{}/work-packages/batch
''')
_register('fulfillment', 'production.manager', '''
POST /work-packages/{}/skip
POST /exceptions/{}/resolve
POST /door-units/{}/changes
''')
_register('fulfillment', 'production.read', 'POST /door-units/{}/exceptions')
_register('fulfillment', 'production.purchase production.warehouse', '''
GET /supplies/workbench
PUT /supplies/{}
''')
_register('fulfillment', 'production.quality', 'POST /door-units/{}/inspections')
_register('fulfillment', 'production.warehouse', '''
POST /door-units/{}/finished-inbound
POST /door-units/{}/component-inbound
POST /door-units/{}/assembly-components/issue
''')
_register('fulfillment', 'finance.receipts', 'POST /door-units/{}/payments')
_register('fulfillment', 'production.shipping', '''
POST /door-units/{}/shipments
POST /shipments/{}/sign
''')
_register('bom', 'production.read', '''
GET /workbench
GET /door-units/{}
GET /door-units/{}/diff/{}/{}
''')
_register('bom', 'production.technical', '''
POST /door-units/{}/generate
PUT /door-units/{}/draft
POST /door-units/{}/verify
POST /door-units/{}/publish
POST /door-units/{}/new-version
''')
_register('sales-orders', 'sales.read finance.read', '''
GET /candidates
GET /
GET /suggestions
GET /receipt-candidates
GET /{}
GET /{}/attachments/{}/file
''')
_register('sales-orders', 'production.sales', '''
POST /
PUT /{}
POST /{}/confirm
POST /{}/retry-provisioning
POST /{}/cancel
POST /{}/attachments
DELETE /{}/attachments/{}
''')
_register('sales-orders', 'finance.receipts', '''
POST /receipts
POST /receipts/{}/reverse
''')
_register('inventory', 'masterdata.read inventory.read production.read', '''
GET /materials
GET /suppliers
GET /supplier-items
GET /bom-rules
GET /warehouses
''')
_register('inventory', 'masterdata.write', '''
POST /materials
PUT /materials/{}
POST /suppliers
PUT /suppliers/{}
POST /supplier-items
PUT /supplier-items/{}
POST /bom-rules
PUT /bom-rules/{}
POST /warehouses
POST /warehouses/{}/locations
GET /master-data/import/template
GET /master-data/import/batches
POST /master-data/import/preview
POST /master-data/import/{}/validate
POST /master-data/import/{}/execute
POST /master-data/import/{}/rollback
''')
_register('inventory', 'inventory.read', '''
GET /warehouse-overview
GET /balances
GET /transactions
GET /adjustments/{}
GET /requirements
GET /requirements/{}
GET /purchasing/shortages
GET /purchasing/orders
GET /purchasing/orders/{}
GET /receipts
GET /receipts/{}
GET /material-flow/pending-issues
GET /material-flow/orders
GET /material-flow/orders/{}
GET /subcontracts
GET /subcontracts/{}
GET /subcontract-receipts
GET /subcontract-receipts/{}
''')
_register('inventory', 'production.warehouse', '''
POST /adjustments
DELETE /adjustments/{}
POST /adjustments/{}/confirm
POST /requirements/{}/reallocate
POST /purchasing/orders/{}/receipts
POST /material-flow/issues
POST /material-flow/returns
POST /material-flow/transfers
POST /material-flow/scraps
POST /subcontracts/{}/receipts
''')
_register('inventory', 'production.technical production.purchase', 'POST /requirement-items/{}/supplement')
_register('inventory', 'production.purchase', '''
POST /purchasing/orders
DELETE /purchasing/orders/{}
POST /purchasing/orders/{}/confirm
POST /purchasing/orders/{}/cancel
POST /subcontracts
''')
_register('inventory', 'production.quality', '''
POST /receipt-items/{}/inspect
POST /subcontract-receipt-items/{}/inspect
''')
_register('operations', 'production.read masterdata.read', 'GET /route-templates')
_register('operations', 'production.technical', 'PUT /route-templates/{}')
_register('operations', 'production.manager payroll.write', 'PUT /piecework/{}/allocations')
_register('operations', 'personnel.read production.read payroll.read', '''
GET /employees
GET /personnel-work
''')
_register('operations', 'personnel.write', '''
POST /employees
PUT /employees/{}
DELETE /employees/{}
''')
_register('operations', 'production.schedule production.manager', 'PUT /door-units/{}/assembly-assignment')
_register('operations', 'attendance.write payroll.read', 'GET /attendance')
_register('operations', 'attendance.write', 'POST /attendance')
_register('operations', 'payroll.read', '''
GET /payroll
GET /payroll/{}
''')
_register('operations', 'payroll.write', '''
POST /payroll/calculate
PUT /payroll/entries/{}
''')
_register('operations', 'payroll.write payroll.approve payroll.unlock', 'PUT /payroll/{}/status')


def route_permissions(method, path):
    normalized = re.sub(r'\{[^}]+\}', '{}', path).rstrip('/')
    return ROUTE_POLICIES.get((method.upper(), normalized)) or ROUTE_POLICIES.get((method.upper(), normalized + '/'))


def require_management_access(request: Request, current_user=Depends(get_current_user)):
    route = request.scope.get('route')
    permissions = route_permissions(request.method, getattr(route, 'path', ''))
    if not permissions:
        raise HTTPException(status_code=403, detail='此经营接口尚未配置访问权限')
    try:
        ensure_business_permission(current_user, *permissions)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
