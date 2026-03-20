from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models import Role, Permission, User
from schemas import (
    RoleCreate, 
    RoleUpdate, 
    RoleResponse,
    PaginatedResponse,
    ResponseModel
)
from auth import get_current_superuser, PermissionChecker

router = APIRouter(prefix="/roles", tags=["角色管理"])


@router.get("", response_model=PaginatedResponse)
async def list_roles(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("role", "read"))
):
    """获取角色列表"""
    query = db.query(Role)
    
    if keyword:
        query = query.filter(
            or_(
                Role.name.contains(keyword),
                Role.code.contains(keyword),
                Role.description.contains(keyword)
            )
        )
    
    total = query.count()
    roles = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        data={
            "items": [RoleResponse.model_validate(r).model_dump() for r in roles],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.get("/all", response_model=ResponseModel)
async def get_all_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """获取所有角色（用于下拉选择）"""
    roles = db.query(Role).filter(Role.is_active == True).all()
    return ResponseModel(
        data={
            "items": [{"id": r.id, "name": r.name, "code": r.code} for r in roles]
        }
    )


@router.get("/{role_id}", response_model=ResponseModel)
async def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("role", "read"))
):
    """获取角色详情"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    return ResponseModel(data=RoleResponse.model_validate(role).model_dump())


@router.post("", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("role", "create"))
):
    """创建角色"""
    # 检查角色代码是否已存在
    existing = db.query(Role).filter(Role.code == role_data.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色代码已存在"
        )
    
    # 检查角色名称是否已存在
    existing = db.query(Role).filter(Role.name == role_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色名称已存在"
        )
    
    # 提取权限ID
    permission_ids = role_data.permission_ids or []
    permissions = db.query(Permission).filter(Permission.id.in_(permission_ids)).all() if permission_ids else []
    
    # 创建角色
    role_data_dict = role_data.model_dump(exclude={"permission_ids"})
    role = Role(**role_data_dict)
    role.permissions = permissions
    
    db.add(role)
    db.commit()
    db.refresh(role)
    
    return ResponseModel(
        message="角色创建成功",
        data=RoleResponse.model_validate(role).model_dump()
    )


@router.put("/{role_id}", response_model=ResponseModel)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("role", "update"))
):
    """更新角色"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    update_data = role_data.model_dump(exclude_unset=True)
    
    # 检查角色代码是否与其他角色冲突
    if "code" in update_data and update_data["code"] != role.code:
        existing = db.query(Role).filter(Role.code == update_data["code"]).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="角色代码已存在"
            )
    
    # 检查角色名称是否与其他角色冲突
    if "name" in update_data and update_data["name"] != role.name:
        existing = db.query(Role).filter(Role.name == update_data["name"]).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="角色名称已存在"
            )
    
    # 更新权限
    if "permission_ids" in update_data:
        permission_ids = update_data.pop("permission_ids")
        if permission_ids is not None:
            permissions = db.query(Permission).filter(Permission.id.in_(permission_ids)).all()
            role.permissions = permissions
    
    # 更新其他字段
    for field, value in update_data.items():
        setattr(role, field, value)
    
    db.commit()
    db.refresh(role)
    
    return ResponseModel(
        message="角色更新成功",
        data=RoleResponse.model_validate(role).model_dump()
    )


@router.delete("/{role_id}", response_model=ResponseModel)
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("role", "delete"))
):
    """删除角色"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    # 检查角色是否被用户使用
    if role.users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该角色已被用户分配，无法删除"
        )
    
    db.delete(role)
    db.commit()
    
    return ResponseModel(message="角色删除成功")


@router.post("/{role_id}/permissions", response_model=ResponseModel)
async def assign_permissions_to_role(
    role_id: int,
    permission_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("role", "update"))
):
    """为角色分配权限"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    permissions = db.query(Permission).filter(Permission.id.in_(permission_ids)).all()
    role.permissions = permissions
    
    db.commit()
    db.refresh(role)
    
    return ResponseModel(
        message="权限分配成功",
        data=RoleResponse.model_validate(role).model_dump()
    )


@router.post("/batch-delete", response_model=ResponseModel)
async def batch_delete_roles(
    role_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("role", "delete"))
):
    """批量删除角色"""
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
    
    if not roles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到要删除的角色"
        )
    
    # 检查是否有角色被用户使用
    for role in roles:
        if role.users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"角色 '{role.name}' 已被用户分配，无法删除"
            )
    
    for role in roles:
        db.delete(role)
    
    db.commit()
    
    return ResponseModel(message=f"成功删除 {len(roles)} 个角色")
