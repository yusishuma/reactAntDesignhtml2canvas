from typing import List, Optional
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from database import get_db
from models import UserLog, User
from schemas import (
    UserLogResponse,
    UserLogQuery,
    LogAction,
    LogStatus,
    PaginatedResponse,
    ResponseModel
)
from auth import get_current_superuser, PermissionChecker

router = APIRouter(prefix="/logs", tags=["用户日志"])


@router.get("", response_model=PaginatedResponse)
async def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user_id: Optional[int] = None,
    action: Optional[LogAction] = None,
    resource: Optional[str] = None,
    status: Optional[LogStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("log", "read"))
):
    """获取日志列表"""
    query = db.query(UserLog)
    
    # 应用过滤器
    if user_id:
        query = query.filter(UserLog.user_id == user_id)
    
    if action:
        query = query.filter(UserLog.action == action)
    
    if resource:
        query = query.filter(UserLog.resource == resource)
    
    if status:
        query = query.filter(UserLog.status == status)
    
    if start_date:
        query = query.filter(UserLog.created_at >= start_date)
    
    if end_date:
        query = query.filter(UserLog.created_at <= end_date)
    
    if keyword:
        query = query.filter(
            UserLog.description.contains(keyword) |
            UserLog.ip_address.contains(keyword) |
            UserLog.user_agent.contains(keyword)
        )
    
    # 按时间倒序排列
    query = query.order_by(UserLog.created_at.desc())
    
    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        data={
            "items": [UserLogResponse.model_validate(log).model_dump() for log in logs],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.get("/statistics", response_model=ResponseModel)
async def get_log_statistics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """获取日志统计信息"""
    query = db.query(UserLog)
    
    if start_date:
        query = query.filter(func.date(UserLog.created_at) >= start_date)
    
    if end_date:
        query = query.filter(func.date(UserLog.created_at) <= end_date)
    
    # 总日志数
    total_logs = query.count()
    
    # 按操作类型统计
    action_stats = db.query(
        UserLog.action,
        func.count(UserLog.id).label('count')
    ).group_by(UserLog.action).all()
    
    # 按状态统计
    status_stats = db.query(
        UserLog.status,
        func.count(UserLog.id).label('count')
    ).group_by(UserLog.status).all()
    
    # 按日期统计（最近7天）
    daily_stats = db.query(
        func.date(UserLog.created_at).label('date'),
        func.count(UserLog.id).label('count')
    ).group_by(func.date(UserLog.created_at)).order_by(func.date(UserLog.created_at).desc()).limit(7).all()
    
    # 活跃用户（操作最多的用户）
    active_users = db.query(
        UserLog.user_id,
        User.username,
        func.count(UserLog.id).label('count')
    ).join(User).group_by(UserLog.user_id, User.username).order_by(func.count(UserLog.id).desc()).limit(10).all()
    
    return ResponseModel(
        data={
            "total_logs": total_logs,
            "action_statistics": [{"action": a.action, "count": a.count} for a in action_stats],
            "status_statistics": [{"status": s.status, "count": s.count} for s in status_stats],
            "daily_statistics": [{"date": str(d.date), "count": d.count} for d in daily_stats],
            "active_users": [{"user_id": u.user_id, "username": u.username, "count": u.count} for u in active_users]
        }
    )


@router.get("/actions", response_model=ResponseModel)
async def get_log_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """获取所有日志操作类型"""
    actions = db.query(UserLog.action).distinct().all()
    return ResponseModel(
        data={"actions": [a[0] for a in actions if a[0]]}
    )


@router.get("/resources", response_model=ResponseModel)
async def get_log_resources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """获取所有日志资源类型"""
    resources = db.query(UserLog.resource).distinct().all()
    return ResponseModel(
        data={"resources": [r[0] for r in resources if r[0]]}
    )


@router.get("/{log_id}", response_model=ResponseModel)
async def get_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("log", "read"))
):
    """获取日志详情"""
    log = db.query(UserLog).filter(UserLog.id == log_id).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="日志不存在"
        )
    return ResponseModel(data=UserLogResponse.model_validate(log).model_dump())


@router.delete("/{log_id}", response_model=ResponseModel)
async def delete_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """删除日志（仅超级管理员）"""
    log = db.query(UserLog).filter(UserLog.id == log_id).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="日志不存在"
        )
    
    db.delete(log)
    db.commit()
    
    return ResponseModel(message="日志删除成功")


@router.post("/batch-delete", response_model=ResponseModel)
async def batch_delete_logs(
    log_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """批量删除日志（仅超级管理员）"""
    logs = db.query(UserLog).filter(UserLog.id.in_(log_ids)).all()
    
    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到要删除的日志"
        )
    
    for log in logs:
        db.delete(log)
    
    db.commit()
    
    return ResponseModel(message=f"成功删除 {len(logs)} 条日志")


@router.post("/cleanup", response_model=ResponseModel)
async def cleanup_old_logs(
    days: int = Query(30, ge=1, description="保留最近多少天的日志"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """清理旧日志（仅超级管理员）"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    deleted_count = db.query(UserLog).filter(UserLog.created_at < cutoff_date).delete(synchronize_session=False)
    db.commit()
    
    return ResponseModel(message=f"成功清理 {deleted_count} 条 {days} 天前的日志")


@router.get("/user/{user_id}", response_model=PaginatedResponse)
async def get_user_logs(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("log", "read"))
):
    """获取指定用户的日志"""
    # 检查用户是否存在
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    query = db.query(UserLog).filter(UserLog.user_id == user_id).order_by(UserLog.created_at.desc())
    
    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        data={
            "items": [UserLogResponse.model_validate(log).model_dump() for log in logs],
            "total": total,
            "page": page,
            "page_size": page_size,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email
            }
        }
    )
