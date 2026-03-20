from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models import Permission, User
from schemas import (
    PermissionCreate, 
    PermissionUpdate, 
    PermissionResponse,
    PaginatedResponse,
    ResponseModel
)
from auth import get_current_superuser, PermissionChecker

router = APIRouter(prefix="/permissions", tags=["权限管理"])


@router.get("", response_model=PaginatedResponse)
async def list_permissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = None,
    resource: Optional[str] = None,
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("permission", "read"))
):
    """获取权限列表"""
    query = db.query(Permission)
    
    if keyword:
        query = query.filter(
            or_(
                Permission.name.contains(keyword),
                Permission.code.contains(keyword),
                Permission.description.contains(keyword)
            )
        )
    
    if resource:
        query = query.filter(Permission.resource == resource)
    
    if action:
        query = query.filter(Permission.action == action)
    
    total = query.count()
    permissions = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        data={
            "items": [PermissionResponse.model_validate(p).model_dump() for p in permissions],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.get("/resources", response_model=ResponseModel)
async def get_resources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """获取所有资源类型列表"""
    resources = db.query(Permission.resource).distinct().all()
    return ResponseModel(data={"resources": [r[0] for r in resources]})


@router.get("/actions", response_model=ResponseModel)
async def get_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """获取所有操作类型列表"""
    actions = db.query(Permission.action).distinct().all()
    return ResponseModel(data={"actions": [a[0] for a in actions]})


@router.get("/{permission_id}", response_model=ResponseModel)
async def get_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("permission", "read"))
):
    """获取权限详情"""
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在"
        )
    return ResponseModel(data=PermissionResponse.model_validate(permission).model_dump())


@router.post("", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def create_permission(
    permission_data: PermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("permission", "create"))
):
    """创建权限"""
    # 检查权限代码是否已存在
    existing = db.query(Permission).filter(Permission.code == permission_data.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="权限代码已存在"
        )
    
    # 检查权限名称是否已存在
    existing = db.query(Permission).filter(Permission.name == permission_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="权限名称已存在"
        )
    
    permission = Permission(**permission_data.model_dump())
    db.add(permission)
    db.commit()
    db.refresh(permission)
    
    return ResponseModel(
        message="权限创建成功",
        data=PermissionResponse.model_validate(permission).model_dump()
    )


@router.put("/{permission_id}", response_model=ResponseModel)
async def update_permission(
    permission_id: int,
    permission_data: PermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("permission", "update"))
):
    """更新权限"""
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在"
        )
    
    update_data = permission_data.model_dump(exclude_unset=True)
    
    # 检查权限代码是否与其他权限冲突
    if "code" in update_data and update_data["code"] != permission.code:
        existing = db.query(Permission).filter(Permission.code == update_data["code"]).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="权限代码已存在"
            )
    
    # 检查权限名称是否与其他权限冲突
    if "name" in update_data and update_data["name"] != permission.name:
        existing = db.query(Permission).filter(Permission.name == update_data["name"]).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="权限名称已存在"
            )
    
    for field, value in update_data.items():
        setattr(permission, field, value)
    
    db.commit()
    db.refresh(permission)
    
    return ResponseModel(
        message="权限更新成功",
        data=PermissionResponse.model_validate(permission).model_dump()
    )


@router.delete("/{permission_id}", response_model=ResponseModel)
async def delete_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("permission", "delete"))
):
    """删除权限"""
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在"
        )
    
    # 检查权限是否被角色使用
    if permission.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该权限已被角色使用，无法删除"
        )
    
    db.delete(permission)
    db.commit()
    
    return ResponseModel(message="权限删除成功")


@router.post("/batch-delete", response_model=ResponseModel)
async def batch_delete_permissions(
    permission_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("permission", "delete"))
):
    """批量删除权限"""
    permissions = db.query(Permission).filter(Permission.id.in_(permission_ids)).all()
    
    if not permissions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到要删除的权限"
        )
    
    # 检查是否有权限被角色使用
    for permission in permissions:
        if permission.roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"权限 '{permission.name}' 已被角色使用，无法删除"
            )
    
    for permission in permissions:
        db.delete(permission)
    
    db.commit()
    
    return ResponseModel(message=f"成功删除 {len(permissions)} 个权限")
