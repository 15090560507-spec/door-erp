"""Business permission configuration without changing passwords or platform roles."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from auth import public_users_map, require_business_admin, user_db
from business_permissions import PERMISSION_LABELS

router = APIRouter(prefix='/api/business-access', tags=['business-access'], dependencies=[Depends(require_business_admin)])


class PermissionAssignment(BaseModel):
    permissions: list[str]
    reason: str = Field(min_length=1, max_length=1000)


@router.get('')
def catalog():
    return {'catalog': [{'key': key, 'label': label} for key, label in PERMISSION_LABELS.items()],
            'users': public_users_map(user_db.load_all_users())}


@router.put('/{uid}')
def assign(uid: str, request: PermissionAssignment, operator=Depends(require_business_admin)):
    try:
        user_db.update_management_permissions(uid, request.permissions, operator, request.reason)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'message': '经营权限已更新，后端立即生效', 'users': public_users_map(user_db.load_all_users())}


@router.get('/{uid}/history')
def history(uid: str):
    users = user_db.load_all_users()
    if uid not in users:
        raise HTTPException(status_code=404, detail='账号不存在')
    return {'events': users[uid].get('permission_audit') or []}
