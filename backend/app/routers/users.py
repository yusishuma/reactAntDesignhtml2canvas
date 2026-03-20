from typing import List, Optional
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, Permission
from app.schemas import (
    UserCreate, UserUpdate, UserResponse, Token,
    PaginatedResponse, PermissionResponse
)
from app.utils import (
    get_password_hash, authenticate_user, create_access_token,
    get_current_active_user, get_current_superuser
)

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱已存在"
        )
    
    hashed_password = get_password_hash(user_data.password)
    user_dict = user_data.model_dump(exclude={"password", "permission_ids"})
    user = User(**user_dict, hashed_password=hashed_password)
    
    if user_data.permission_ids:
        permissions = db.query(Permission).filter(
            Permission.id.in_(user_data.permission_ids)
        ).all()
        user.permissions = permissions
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已被禁用"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    update_data = user_data.model_dump(exclude_unset=True)
    
    if "username" in update_data and update_data["username"] != current_user.username:
        existing = db.query(User).filter(
            User.username == update_data["username"]
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
    
    if "email" in update_data and update_data["email"] != current_user.email:
        existing = db.query(User).filter(
            User.email == update_data["email"]
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已存在"
            )
    
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    for key, value in update_data.items():
        if key != "permission_ids":
            setattr(current_user, key, value)
    
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/", response_model=PaginatedResponse)
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    username: Optional[str] = None,
    email: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_superuser: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    query = db.query(User)
    
    if username:
        query = query.filter(User.username.contains(username))
    if email:
        query = query.filter(User.email.contains(email))
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if is_superuser is not None:
        query = query.filter(User.is_superuser == is_superuser)
    
    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[UserResponse.model_validate(u) for u in users]
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    update_data = user_data.model_dump(exclude_unset=True)
    
    if "username" in update_data and update_data["username"] != user.username:
        existing = db.query(User).filter(
            User.id != user_id,
            User.username == update_data["username"]
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
    
    if "email" in update_data and update_data["email"] != user.email:
        existing = db.query(User).filter(
            User.id != user_id,
            User.email == update_data["email"]
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已存在"
            )
    
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    if "permission_ids" in update_data:
        permission_ids = update_data.pop("permission_ids")
        permissions = db.query(Permission).filter(
            Permission.id.in_(permission_ids)
        ).all()
        user.permissions = permissions
    
    for key, value in update_data.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    db.delete(user)
    db.commit()
    return None


@router.post("/{user_id}/permissions", response_model=UserResponse)
async def assign_permissions(
    user_id: int,
    permission_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    permissions = db.query(Permission).filter(
        Permission.id.in_(permission_ids)
    ).all()
    user.permissions = permissions
    
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}/permissions", response_model=List[PermissionResponse])
async def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return user.permissions
