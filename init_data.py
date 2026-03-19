from app import create_app
from extensions import db
from models import Permission, Role, User

def init_data():
    app = create_app()
    with app.app_context():
        # 创建基础权限
        permissions = [
            # 用户管理权限
            {'name': 'user:view', 'description': '查看用户', 'module': 'user'},
            {'name': 'user:create', 'description': '创建用户', 'module': 'user'},
            {'name': 'user:update', 'description': '更新用户', 'module': 'user'},
            {'name': 'user:delete', 'description': '删除用户', 'module': 'user'},
            
            # 权限管理权限
            {'name': 'permission:view', 'description': '查看权限', 'module': 'permission'},
            {'name': 'permission:create', 'description': '创建权限', 'module': 'permission'},
            {'name': 'permission:update', 'description': '更新权限', 'module': 'permission'},
            {'name': 'permission:delete', 'description': '删除权限', 'module': 'permission'},
            
            # 角色管理权限
            {'name': 'role:view', 'description': '查看角色', 'module': 'role'},
            {'name': 'role:create', 'description': '创建角色', 'module': 'role'},
            {'name': 'role:update', 'description': '更新角色', 'module': 'role'},
            {'name': 'role:delete', 'description': '删除角色', 'module': 'role'},
            
            # 日志管理权限
            {'name': 'log:view', 'description': '查看日志', 'module': 'log'},
            {'name': 'log:delete', 'description': '删除日志', 'module': 'log'},
        ]

        for perm_data in permissions:
            if not Permission.query.filter_by(name=perm_data['name']).first():
                perm = Permission(**perm_data)
                db.session.add(perm)
        
        db.session.commit()

        # 创建管理员角色
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(
                name='admin',
                description='系统管理员，拥有所有权限',
                is_active=True
            )
            # 分配所有权限
            all_permissions = Permission.query.all()
            admin_role.permissions = all_permissions
            db.session.add(admin_role)
            db.session.commit()

        # 创建普通用户角色
        user_role = Role.query.filter_by(name='user').first()
        if not user_role:
            user_role = Role(
                name='user',
                description='普通用户，仅有基本查看权限',
                is_active=True
            )
            # 分配查看权限
            view_permissions = Permission.query.filter(
                Permission.name.in_(['user:view', 'permission:view', 'role:view', 'log:view'])
            ).all()
            user_role.permissions = view_permissions
            db.session.add(user_role)
            db.session.commit()

        # 创建管理员用户
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@example.com',
                full_name='系统管理员',
                is_active=True
            )
            admin_user.password = 'admin123'  # 生产环境请修改为强密码
            admin_user.roles = [admin_role]
            db.session.add(admin_user)
            db.session.commit()

        # 创建测试用户
        test_user = User.query.filter_by(username='test').first()
        if not test_user:
            test_user = User(
                username='test',
                email='test@example.com',
                full_name='测试用户',
                is_active=True
            )
            test_user.password = 'test123'
            test_user.roles = [user_role]
            db.session.add(test_user)
            db.session.commit()

        print('初始化数据完成！')
        print('管理员账号: admin / admin123')
        print('测试用户账号: test / test123')

if __name__ == '__main__':
    init_data()
