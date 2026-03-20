from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Permission, User
from app.schemas import PermissionCreate, PermissionUpdate, PermissionResponse, PaginatedResponse
from app.utils import get_current_active_user, get_current_superuser

router = APIRouter(prefix="/permissions", tags=["权限管理"])


@router.post("/", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def create_permission(
    permission_data: PermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    existing = db.query(Permission).filter(
        (Permission.name == permission_data.name) | (Permission.code == permission_data.code)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="权限名称或代码已存在"
        )
    
    permission = Permission(**permission_data.model_dump())
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


@router.get("/", response_model=PaginatedResponse)
async def get_permissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    name: Optional[str] = None,
    code: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Permission)
    
    if name:
        query = query.filter(Permission.name.contains(name))
    if code:
        query = query.filter(Permission.code.contains(code))
    if is_active is not None:
        query = query.filter(Permission.is_active == is_active)
    
    total = query.count()
    permissions = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[PermissionResponse.model_validate(p) for p in permissions]
    )


@router.get("/{permission_id}", response_model=PermissionResponse)
async def get_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在"
        )
    return permission


@router.put("/{permission_id}", response_model=PermissionResponse)
async def update_permission(
    permission_id: int,
    permission_data: PermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在"
        )
    
    update_data = permission_data.model_dump(exclude_unset=True)
    
    if "name" in update_data or "code" in update_data:
        existing = db.query(Permission).filter(
            Permission.id != permission_id,
            (Permission.name == update_data.get("name", "")) | 
            (Permission.code == update_data.get("code", ""))
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="权限名称或代码已存在"
            )
    
    for key, value in update_data.items():
        setattr(permission, key, value)
    
    db.commit()
    db.refresh(permission)
    return permission


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在"
        )
    
    db.delete(permission)
    db.commit()
    return None


@router.get("/{permission_id}/users", response_model=List[dict])
async def get_permission_users(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在"
        )
    
    return [{"id": user.id, "username": user.username, "email": user.email} for user in permission.users]
