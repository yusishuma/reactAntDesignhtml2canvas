from flask import request
from flask_restful import Resource
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import Permission, Role, User, UserLog
from extensions import db
from datetime import datetime
from sqlalchemy import or_

class PermissionListResource(Resource):
    """权限列表资源"""
    @jwt_required()
    def get(self):
        """获取权限列表，支持分页和筛选"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        module = request.args.get('module')
        keyword = request.args.get('keyword')

        query = Permission.query
        if module:
            query = query.filter_by(module=module)
        if keyword:
            query = query.filter(or_(
                Permission.name.like(f'%{keyword}%'),
                Permission.description.like(f'%{keyword}%')
            ))

        permissions = query.order_by(Permission.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return {
            'data': [p.to_dict() for p in permissions.items],
            'total': permissions.total,
            'page': page,
            'per_page': per_page,
            'pages': permissions.pages
        }, 200

    @jwt_required()
    def post(self):
        """创建新权限"""
        data = request.get_json()

        if Permission.query.filter_by(name=data['name']).first():
            return {'message': '权限名称已存在'}, 400

        permission = Permission(
            name=data['name'],
            description=data.get('description', ''),
            module=data.get('module', '')
        )

        db.session.add(permission)
        db.session.commit()

        return {
            'message': '权限创建成功',
            'data': permission.to_dict()
        }, 201

class PermissionResource(Resource):
    """单权限资源"""
    @jwt_required()
    def get(self, permission_id):
        """获取单个权限详情"""
        permission = Permission.query.get_or_404(permission_id)
        return {'data': permission.to_dict()}, 200

    @jwt_required()
    def put(self, permission_id):
        """更新权限"""
        permission = Permission.query.get_or_404(permission_id)
        data = request.get_json()

        if 'name' in data and data['name'] != permission.name:
            if Permission.query.filter_by(name=data['name']).first():
                return {'message': '权限名称已存在'}, 400
            permission.name = data['name']

        if 'description' in data:
            permission.description = data['description']
        if 'module' in data:
            permission.module = data['module']

        db.session.commit()
        return {
            'message': '权限更新成功',
            'data': permission.to_dict()
        }, 200

    @jwt_required()
    def delete(self, permission_id):
        """删除权限"""
        permission = Permission.query.get_or_404(permission_id)
        db.session.delete(permission)
        db.session.commit()
        return {'message': '权限删除成功'}, 200

class RoleListResource(Resource):
    """角色列表资源"""
    @jwt_required()
    def get(self):
        """获取角色列表"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        keyword = request.args.get('keyword')

        query = Role.query
        if keyword:
            query = query.filter(or_(
                Role.name.like(f'%{keyword}%'),
                Role.description.like(f'%{keyword}%')
            ))

        roles = query.order_by(Role.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return {
            'data': [r.to_dict() for r in roles.items],
            'total': roles.total,
            'page': page,
            'per_page': per_page,
            'pages': roles.pages
        }, 200

    @jwt_required()
    def post(self):
        """创建新角色"""
        data = request.get_json()

        if Role.query.filter_by(name=data['name']).first():
            return {'message': '角色名称已存在'}, 400

        role = Role(
            name=data['name'],
            description=data.get('description', ''),
            is_active=data.get('is_active', True)
        )

        # 关联权限
        if 'permission_ids' in data:
            permissions = Permission.query.filter(Permission.id.in_(data['permission_ids'])).all()
            role.permissions = permissions

        db.session.add(role)
        db.session.commit()

        return {
            'message': '角色创建成功',
            'data': role.to_dict()
        }, 201

class RoleResource(Resource):
    """单角色资源"""
    @jwt_required()
    def get(self, role_id):
        """获取单个角色详情"""
        role = Role.query.get_or_404(role_id)
        return {'data': role.to_dict()}, 200

    @jwt_required()
    def put(self, role_id):
        """更新角色"""
        role = Role.query.get_or_404(role_id)
        data = request.get_json()

        if 'name' in data and data['name'] != role.name:
            if Role.query.filter_by(name=data['name']).first():
                return {'message': '角色名称已存在'}, 400
            role.name = data['name']

        if 'description' in data:
            role.description = data['description']
        if 'is_active' in data:
            role.is_active = data['is_active']

        # 更新权限关联
        if 'permission_ids' in data:
            permissions = Permission.query.filter(Permission.id.in_(data['permission_ids'])).all()
            role.permissions = permissions

        db.session.commit()
        return {
            'message': '角色更新成功',
            'data': role.to_dict()
        }, 200

    @jwt_required()
    def delete(self, role_id):
        """删除角色"""
        role = Role.query.get_or_404(role_id)
        db.session.delete(role)
        db.session.commit()
        return {'message': '角色删除成功'}, 200

class UserListResource(Resource):
    """用户列表资源"""
    @jwt_required()
    def get(self):
        """获取用户列表"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        keyword = request.args.get('keyword')
        is_active = request.args.get('is_active')

        query = User.query
        if keyword:
            query = query.filter(or_(
                User.username.like(f'%{keyword}%'),
                User.email.like(f'%{keyword}%'),
                User.full_name.like(f'%{keyword}%')
            ))
        if is_active is not None:
            query = query.filter_by(is_active=(is_active.lower() == 'true'))

        users = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return {
            'data': [u.to_dict() for u in users.items],
            'total': users.total,
            'page': page,
            'per_page': per_page,
            'pages': users.pages
        }, 200

    def post(self):
        """创建新用户（注册）"""
        data = request.get_json()

        if User.query.filter_by(username=data['username']).first():
            return {'message': '用户名已存在'}, 400
        if User.query.filter_by(email=data['email']).first():
            return {'message': '邮箱已存在'}, 400

        user = User(
            username=data['username'],
            email=data['email'],
            full_name=data.get('full_name', ''),
            phone=data.get('phone', '')
        )
        user.password = data['password']

        # 默认角色（可选）
        if 'role_ids' in data:
            roles = Role.query.filter(Role.id.in_(data['role_ids'])).all()
            user.roles = roles

        db.session.add(user)
        db.session.commit()

        return {
            'message': '用户创建成功',
            'data': user.to_dict()
        }, 201

class UserResource(Resource):
    """单用户资源"""
    @jwt_required()
    def get(self, user_id):
        """获取单个用户详情"""
        user = User.query.get_or_404(user_id)
        return {'data': user.to_dict()}, 200

    @jwt_required()
    def put(self, user_id):
        """更新用户信息"""
        user = User.query.get_or_404(user_id)
        data = request.get_json()

        if 'username' in data and data['username'] != user.username:
            if User.query.filter_by(username=data['username']).first():
                return {'message': '用户名已存在'}, 400
            user.username = data['username']

        if 'email' in data and data['email'] != user.email:
            if User.query.filter_by(email=data['email']).first():
                return {'message': '邮箱已存在'}, 400
            user.email = data['email']

        if 'full_name' in data:
            user.full_name = data['full_name']
        if 'phone' in data:
            user.phone = data['phone']
        if 'avatar' in data:
            user.avatar = data['avatar']
        if 'is_active' in data:
            user.is_active = data['is_active']

        # 更新密码（如果提供）
        if 'password' in data:
            user.password = data['password']

        # 更新角色关联
        if 'role_ids' in data:
            roles = Role.query.filter(Role.id.in_(data['role_ids'])).all()
            user.roles = roles

        db.session.commit()
        return {
            'message': '用户更新成功',
            'data': user.to_dict()
        }, 200

    @jwt_required()
    def delete(self, user_id):
        """删除用户"""
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return {'message': '用户删除成功'}, 200

class UserLoginResource(Resource):
    """用户登录"""
    def post(self):
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        user = User.query.filter_by(username=username).first()
        if not user or not user.verify_password(password):
            # 记录登录失败日志
            log = UserLog(
                user_id=user.id if user else None,
                username=username,
                action='login',
                description='登录失败：用户名或密码错误',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
                status='failed'
            )
            db.session.add(log)
            db.session.commit()
            return {'message': '用户名或密码错误'}, 401

        if not user.is_active:
            return {'message': '账户已被禁用'}, 403

        # 更新最后登录时间
        user.last_login = datetime.utcnow()
        db.session.commit()

        # 生成访问令牌
        access_token = create_access_token(identity=user.id)

        # 记录登录成功日志
        log = UserLog(
            user_id=user.id,
            username=user.username,
            action='login',
            description='登录成功',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            status='success'
        )
        db.session.add(log)
        db.session.commit()

        return {
            'message': '登录成功',
            'access_token': access_token,
            'user': user.to_dict()
        }, 200

class UserProfileResource(Resource):
    """获取当前登录用户信息"""
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        user = User.query.get_or_404(user_id)
        return {'data': user.to_dict()}, 200

class UserLogResource(Resource):
    """用户日志资源"""
    @jwt_required()
    def get(self):
        """获取用户操作日志列表"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        user_id = request.args.get('user_id', type=int)
        action = request.args.get('action')
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = UserLog.query

        if user_id:
            query = query.filter_by(user_id=user_id)
        if action:
            query = query.filter_by(action=action)
        if status:
            query = query.filter_by(status=status)
        if start_date:
            query = query.filter(UserLog.created_at >= start_date)
        if end_date:
            query = query.filter(UserLog.created_at <= end_date)

        logs = query.order_by(UserLog.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return {
            'data': [l.to_dict() for l in logs.items],
            'total': logs.total,
            'page': page,
            'per_page': per_page,
            'pages': logs.pages
        }, 200

class UserLogDetailResource(Resource):
    """单条日志详情"""
    @jwt_required()
    def get(self, log_id):
        log = UserLog.query.get_or_404(log_id)
        return {'data': log.to_dict()}, 200

def initialize_routes(api):
    """初始化路由"""
    # 权限管理
    api.add_resource(PermissionListResource, '/api/permissions')
    api.add_resource(PermissionResource, '/api/permissions/<int:permission_id>')

    # 角色管理
    api.add_resource(RoleListResource, '/api/roles')
    api.add_resource(RoleResource, '/api/roles/<int:role_id>')

    # 用户管理
    api.add_resource(UserListResource, '/api/users')
    api.add_resource(UserResource, '/api/users/<int:user_id>')
    api.add_resource(UserLoginResource, '/api/auth/login')
    api.add_resource(UserProfileResource, '/api/auth/profile')

    # 用户日志
    api.add_resource(UserLogResource, '/api/logs')
    api.add_resource(UserLogDetailResource, '/api/logs/<int:log_id>')
