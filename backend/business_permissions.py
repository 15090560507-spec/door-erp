"""Canonical business permissions; no dependency on HTTP or user storage."""
PERMISSION_LABELS = {
    'sales.read': '查看销售订单', 'production.sales': '创建/确认销售订单',
    'production.read': '查看生产履约', 'production.technical': 'BOM与技术准备',
    'production.purchase': '采购下单与外协', 'production.warehouse': '仓库出入库与调整',
    'production.schedule': '生产排单与人员分配', 'production.cutting': '算料与下料',
    'production.worker': '工序报工', 'production.quality': '质量检验',
    'production.shipping': '出库发货与签收', 'production.manager': '生产变更与异常处理',
    'inventory.read': '查看库存与采购', 'masterdata.read': '查看基础资料',
    'masterdata.write': '维护基础资料', 'personnel.read': '查看人员工作',
    'personnel.write': '维护人员与薪资档案', 'attendance.write': '考勤登记',
    'payroll.read': '查看工资', 'payroll.write': '计算/编辑并提交工资',
    'payroll.approve': '工资审核与锁定', 'payroll.unlock': '撤销工资审批/解锁',
    'finance.read': '查看收款资料', 'finance.receipts': '登记/冲销收款',
    'finance.release': '审批欠款发货放行',
}
ALL_BUSINESS_PERMISSIONS = frozenset(PERMISSION_LABELS)
ROLE_DEFAULTS = {
    '录入员': {'sales.read', 'production.sales', 'production.read'},
    '绘图员': {'production.read', 'production.technical', 'production.cutting'},
    '初审员': {'production.read', 'masterdata.read'},
    '总工': {'production.read', 'production.technical', 'production.cutting', 'production.manager'},
    '采购员': {'production.purchase'}, '仓管员': {'production.warehouse'},
    '生产主管': {'production.schedule', 'production.worker', 'production.manager'},
    '质检员': {'production.quality'}, '发货员': {'production.shipping'},
    '工人': {'production.worker'},
    '财务': {'finance.receipts', 'payroll.write'},
}
IMPLIED = {
    'production.sales': {'sales.read', 'production.read'},
    'production.technical': {'production.read', 'masterdata.read'},
    'production.purchase': {'inventory.read', 'masterdata.read', 'production.read'},
    'production.warehouse': {'inventory.read', 'masterdata.read', 'production.read'},
    'production.schedule': {'production.read', 'personnel.read'},
    'production.cutting': {'production.read', 'masterdata.read'},
    'production.worker': {'production.read'}, 'production.quality': {'production.read', 'inventory.read'},
    'production.shipping': {'production.read'}, 'production.manager': {'production.read', 'personnel.read'},
    'masterdata.write': {'masterdata.read'}, 'personnel.write': {'personnel.read'},
    'attendance.write': {'personnel.read'},
    'payroll.write': {'payroll.read', 'personnel.read'},
    'payroll.approve': {'payroll.read', 'personnel.read'}, 'payroll.unlock': {'payroll.read', 'personnel.read'},
    'finance.receipts': {'finance.read', 'sales.read'}, 'finance.release': {'finance.read', 'production.read'},
}


def is_business_admin(user):
    return bool(user and (user.get('role') == '超级管理员' or user.get('uid') == 'A'))


def business_permissions(user):
    if not user:
        return set()
    if is_business_admin(user):
        return set(ALL_BUSINESS_PERMISSIONS)
    assigned = user.get('management_permissions')
    if assigned is None:
        assigned = set(ROLE_DEFAULTS.get(user.get('role'), set())) | set(user.get('permissions') or [])
    result = set(assigned) & ALL_BUSINESS_PERMISSIONS
    for permission in tuple(result):
        result.update(IMPLIED.get(permission, set()))
    return result


def ensure_business_permission(user, *permissions):
    if not set(permissions).intersection(business_permissions(user)):
        raise PermissionError('权限不足：' + ' / '.join(PERMISSION_LABELS.get(p, p) for p in permissions))
