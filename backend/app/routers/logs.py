from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import User, UserLog
from app.schemas import UserLogCreate, UserLogResponse, PaginatedResponse
from app.utils import get_current_active_user, get_current_superuser

router = APIRouter(prefix="/logs", tags=["用户日志"])


async def log_user_action(
    db: Session,
    user: User,
    action: str,
    request: Request,
    description: Optional[str] = None,
    status_code: int = 200
):
    log = UserLog(
        user_id=user.id,
        action=action,
        description=description,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_url=str(request.url),
        request_method=request.method,
        status_code=status_code
    )
    db.add(log)
    db.commit()


@router.post("/", response_model=UserLogResponse, status_code=status.HTTP_201_CREATED)
async def create_log(
    log_data: UserLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    user = db.query(User).filter(User.id == log_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    log = UserLog(**log_data.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("/", response_model=PaginatedResponse)
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    ip_address: Optional[str] = None,
    status_code: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    query = db.query(UserLog)
    
    if user_id:
        query = query.filter(UserLog.user_id == user_id)
    if action:
        query = query.filter(UserLog.action.contains(action))
    if start_date:
        query = query.filter(UserLog.created_at >= start_date)
    if end_date:
        query = query.filter(UserLog.created_at <= end_date)
    if ip_address:
        query = query.filter(UserLog.ip_address.contains(ip_address))
    if status_code:
        query = query.filter(UserLog.status_code == status_code)
    
    query = query.order_by(desc(UserLog.created_at))
    
    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[UserLogResponse.model_validate(log) for log in logs]
    )


@router.get("/me", response_model=PaginatedResponse)
async def get_my_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(UserLog).filter(UserLog.user_id == current_user.id)
    
    if action:
        query = query.filter(UserLog.action.contains(action))
    if start_date:
        query = query.filter(UserLog.created_at >= start_date)
    if end_date:
        query = query.filter(UserLog.created_at <= end_date)
    
    query = query.order_by(desc(UserLog.created_at))
    
    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[UserLogResponse.model_validate(log) for log in logs]
    )


@router.get("/{log_id}", response_model=UserLogResponse)
async def get_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    log = db.query(UserLog).filter(UserLog.id == log_id).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="日志不存在"
        )
    
    if not current_user.is_superuser and log.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权查看此日志"
        )
    
    return log


@router.get("/user/{user_id}", response_model=PaginatedResponse)
async def get_user_logs(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    query = db.query(UserLog).filter(UserLog.user_id == user_id)
    
    if action:
        query = query.filter(UserLog.action.contains(action))
    if start_date:
        query = query.filter(UserLog.created_at >= start_date)
    if end_date:
        query = query.filter(UserLog.created_at <= end_date)
    
    query = query.order_by(desc(UserLog.created_at))
    
    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[UserLogResponse.model_validate(log) for log in logs]
    )


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    log = db.query(UserLog).filter(UserLog.id == log_id).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="日志不存在"
        )
    
    db.delete(log)
    db.commit()
    return None


@router.delete("/user/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_logs(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    db.query(UserLog).filter(UserLog.user_id == user_id).delete()
    db.commit()
    return None
