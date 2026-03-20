from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models import User, Role, UserLog
from schemas import (
    UserCreate, 
    UserUpdate, 
    UserResponse,
    UserSimple,
    PaginatedResponse,
    ResponseModel,
    LoginRequest,
    Token
)
from auth import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    get_current_user,
    get_current_superuser,
    PermissionChecker,
    get_settings
)

router = APIRouter(prefix="/users", tags=["用户管理"])
settings = get_settings()


def create_log(db: Session, user_id: int, action: str, resource: str = None, 
               resource_id: int = None, description: str = None, 
               ip_address: str = None, user_agent: str = None, status: str = "success"):
    """创建用户日志"""
    log = UserLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status
    )
    db.add(log)
    db.commit()


@router.post("/login", response_model=ResponseModel)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """用户登录"""
    user = db.query(User).filter(User.username == login_data.username).first()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        # 记录失败日志
        if user:
            create_log(
                db, user.id, "login", status="failed",
                description="登录失败：密码错误",
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    if not user.is_active:
        create_log(
            db, user.id, "login", status="failed",
            description="登录失败：用户已被禁用",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    
    # 更新最后登录时间
    user.last_login = datetime.utcnow()
    db.commit()
    
    # 创建访问令牌
    access_token, expire = create_access_token(data={"sub": user.username})
    
    # 记录登录日志
    create_log(
        db, user.id, "login",
        description="用户登录成功",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return ResponseModel(
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": UserResponse.model_validate(user).model_dump()
        }
    )


@router.post("/logout", response_model=ResponseModel)
async def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """用户登出"""
    create_log(
        db, current_user.id, "logout",
        description="用户登出",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return ResponseModel(message="登出成功")


@router.get("/me", response_model=ResponseModel)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前登录用户信息"""
    return ResponseModel(data=UserResponse.model_validate(current_user).model_dump())


@router.put("/me", response_model=ResponseModel)
async def update_current_user(
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新当前用户信息"""
    update_data = user_data.model_dump(exclude_unset=True)
    
    # 普通用户不能修改自己的角色和状态
    update_data.pop("role_ids", None)
    update_data.pop("is_active", None)
    
    # 检查用户名是否冲突
    if "username" in update_data and update_data["username"] != current_user.username:
        existing = db.query(User).filter(User.username == update_data["username"]).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
    
    # 检查邮箱是否冲突
    if "email" in update_data and update_data["email"] != current_user.email:
        existing = db.query(User).filter(User.email == update_data["email"]).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已存在"
            )
    
    # 处理密码更新
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return ResponseModel(
        message="个人信息更新成功",
        data=UserResponse.model_validate(current_user).model_dump()
    )


@router.get("", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user", "read"))
):
    """获取用户列表"""
    query = db.query(User)
    
    if keyword:
        query = query.filter(
            or_(
                User.username.contains(keyword),
                User.email.contains(keyword),
                User.full_name.contains(keyword),
                User.phone.contains(keyword)
            )
        )
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        data={
            "items": [UserResponse.model_validate(u).model_dump() for u in users],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.get("/{user_id}", response_model=ResponseModel)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user", "read"))
):
    """获取用户详情"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return ResponseModel(data=UserResponse.model_validate(user).model_dump())


@router.post("", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user", "create"))
):
    """创建用户"""
    # 检查用户名是否已存在
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否已存在
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已存在"
        )
    
    # 提取角色ID
    role_ids = user_data.role_ids or []
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all() if role_ids else []
    
    # 创建用户
    user_data_dict = user_data.model_dump(exclude={"password", "role_ids"})
    user = User(
        **user_data_dict,
        hashed_password=get_password_hash(user_data.password)
    )
    user.roles = roles
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # 记录日志
    create_log(
        db, current_user.id, "create", "user", user.id,
        description=f"创建用户: {user.username}",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return ResponseModel(
        message="用户创建成功",
        data=UserResponse.model_validate(user).model_dump()
    )


@router.put("/{user_id}", response_model=ResponseModel)
async def update_user(
    request: Request,
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user", "update"))
):
    """更新用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 不能修改超级管理员（除非自己是超级管理员）
    if user.is_superuser and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改超级管理员"
        )
    
    update_data = user_data.model_dump(exclude_unset=True)
    
    # 检查用户名是否与其他用户冲突
    if "username" in update_data and update_data["username"] != user.username:
        existing = db.query(User).filter(User.username == update_data["username"]).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
    
    # 检查邮箱是否与其他用户冲突
    if "email" in update_data and update_data["email"] != user.email:
        existing = db.query(User).filter(User.email == update_data["email"]).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已存在"
            )
    
    # 处理密码更新
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    # 更新角色
    if "role_ids" in update_data:
        role_ids = update_data.pop("role_ids")
        if role_ids is not None:
            roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
            user.roles = roles
    
    # 更新其他字段
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    # 记录日志
    create_log(
        db, current_user.id, "update", "user", user.id,
        description=f"更新用户: {user.username}",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return ResponseModel(
        message="用户更新成功",
        data=UserResponse.model_validate(user).model_dump()
    )


@router.delete("/{user_id}", response_model=ResponseModel)
async def delete_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user", "delete"))
):
    """删除用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除当前登录用户"
        )
    
    # 不能删除超级管理员（除非自己是超级管理员）
    if user.is_superuser and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除超级管理员"
        )
    
    username = user.username
    db.delete(user)
    db.commit()
    
    # 记录日志
    create_log(
        db, current_user.id, "delete", "user", user_id,
        description=f"删除用户: {username}",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return ResponseModel(message="用户删除成功")


@router.post("/{user_id}/roles", response_model=ResponseModel)
async def assign_roles_to_user(
    request: Request,
    user_id: int,
    role_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user", "update"))
):
    """为用户分配角色"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
    user.roles = roles
    
    db.commit()
    db.refresh(user)
    
    # 记录日志
    create_log(
        db, current_user.id, "update", "user", user.id,
        description=f"为用户 {user.username} 分配角色",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return ResponseModel(
        message="角色分配成功",
        data=UserResponse.model_validate(user).model_dump()
    )


@router.post("/batch-delete", response_model=ResponseModel)
async def batch_delete_users(
    request: Request,
    user_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("user", "delete"))
):
    """批量删除用户"""
    # 不能删除自己
    if current_user.id in user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除当前登录用户"
        )
    
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    
    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到要删除的用户"
        )
    
    deleted_count = 0
    for user in users:
        # 跳过超级管理员
        if user.is_superuser and not current_user.is_superuser:
            continue
        
        username = user.username
        db.delete(user)
        deleted_count += 1
        
        # 记录日志
        create_log(
            db, current_user.id, "delete", "user", user.id,
            description=f"删除用户: {username}",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
    
    db.commit()
    
    return ResponseModel(message=f"成功删除 {deleted_count} 个用户")


@router.post("/{user_id}/reset-password", response_model=ResponseModel)
async def reset_user_password(
    request: Request,
    user_id: int,
    new_password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """重置用户密码（仅超级管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    user.hashed_password = get_password_hash(new_password)
    db.commit()
    
    # 记录日志
    create_log(
        db, current_user.id, "update", "user", user.id,
        description=f"重置用户 {user.username} 的密码",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return ResponseModel(message="密码重置成功")
