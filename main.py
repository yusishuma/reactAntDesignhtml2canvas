from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import engine, Base
from config import get_settings
from models import User, Role, Permission, UserLog
from auth import get_password_hash
from routers import users, roles, permissions, logs

settings = get_settings()


async def init_db():
    """初始化数据库和默认数据"""
    from sqlalchemy.orm import Session
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # 创建默认权限
        default_permissions = [
            # 用户管理权限
            {"name": "用户查看", "code": "user:read", "resource": "user", "action": "read", "description": "查看用户信息"},
            {"name": "用户创建", "code": "user:create", "resource": "user", "action": "create", "description": "创建用户"},
            {"name": "用户更新", "code": "user:update", "resource": "user", "action": "update", "description": "更新用户信息"},
            {"name": "用户删除", "code": "user:delete", "resource": "user", "action": "delete", "description": "删除用户"},
            # 角色管理权限
            {"name": "角色查看", "code": "role:read", "resource": "role", "action": "read", "description": "查看角色信息"},
            {"name": "角色创建", "code": "role:create", "resource": "role", "action": "create", "description": "创建角色"},
            {"name": "角色更新", "code": "role:update", "resource": "role", "action": "update", "description": "更新角色信息"},
            {"name": "角色删除", "code": "role:delete", "resource": "role", "action": "delete", "description": "删除角色"},
            # 权限管理权限
            {"name": "权限查看", "code": "permission:read", "resource": "permission", "action": "read", "description": "查看权限信息"},
            {"name": "权限创建", "code": "permission:create", "resource": "permission", "action": "create", "description": "创建权限"},
            {"name": "权限更新", "code": "permission:update", "resource": "permission", "action": "update", "description": "更新权限信息"},
            {"name": "权限删除", "code": "permission:delete", "resource": "permission", "action": "delete", "description": "删除权限"},
            # 日志管理权限
            {"name": "日志查看", "code": "log:read", "resource": "log", "action": "read", "description": "查看系统日志"},
        ]
        
        permission_objects = []
        for perm_data in default_permissions:
            existing = db.query(Permission).filter(Permission.code == perm_data["code"]).first()
            if not existing:
                perm = Permission(**perm_data)
                db.add(perm)
                permission_objects.append(perm)
            else:
                permission_objects.append(existing)
        
        db.commit()
        
        # 创建默认管理员角色
        admin_role = db.query(Role).filter(Role.code == "admin").first()
        if not admin_role:
            admin_role = Role(
                name="管理员",
                code="admin",
                description="系统管理员，拥有所有权限"
            )
            db.add(admin_role)
            db.commit()
            db.refresh(admin_role)
        
        # 为管理员角色分配所有权限
        all_permissions = db.query(Permission).all()
        admin_role.permissions = all_permissions
        db.commit()
        
        # 创建默认超级管理员用户
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@example.com",
                full_name="系统管理员",
                hashed_password=get_password_hash("admin123"),
                is_active=True,
                is_superuser=True
            )
            admin_user.roles = [admin_role]
            db.add(admin_user)
            db.commit()
            print("=" * 50)
            print("默认管理员账户已创建:")
            print("用户名: admin")
            print("密码: admin123")
            print("=" * 50)
        
        print("数据库初始化完成")
        
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建表
    Base.metadata.create_all(bind=engine)
    # 初始化默认数据
    await init_db()
    yield
    # 关闭时的清理工作


app = FastAPI(
    title=settings.APP_NAME,
    description="用户管理系统 RESTful API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(permissions.router)
app.include_router(logs.router)


@app.get("/", tags=["根路径"])
async def root():
    return {
        "message": "欢迎使用用户管理系统 API",
        "docs": "/docs",
        "version": "1.0.0"
    }


@app.get("/health", tags=["健康检查"])
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
