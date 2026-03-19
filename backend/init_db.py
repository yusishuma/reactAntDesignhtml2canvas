from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import User, Permission
from app.utils import get_password_hash


def init_db():
    Base.metadata.create_all(bind=engine)
    
    db: Session = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                full_name="超级管理员",
                is_active=True,
                is_superuser=True
            )
            db.add(admin_user)
            print("创建超级管理员用户: admin / admin123")
        
        default_permissions = [
            {"name": "用户查看", "code": "user:read", "description": "查看用户列表和详情"},
            {"name": "用户管理", "code": "user:write", "description": "创建、编辑、删除用户"},
            {"name": "权限查看", "code": "permission:read", "description": "查看权限列表和详情"},
            {"name": "权限管理", "code": "permission:write", "description": "创建、编辑、删除权限"},
            {"name": "日志查看", "code": "log:read", "description": "查看用户操作日志"},
            {"name": "日志管理", "code": "log:write", "description": "删除用户操作日志"},
        ]
        
        for perm_data in default_permissions:
            existing = db.query(Permission).filter(Permission.code == perm_data["code"]).first()
            if not existing:
                permission = Permission(**perm_data)
                db.add(permission)
                print(f"创建权限: {perm_data['name']}")
        
        db.commit()
        print("数据库初始化完成!")
        
    except Exception as e:
        print(f"初始化失败: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
