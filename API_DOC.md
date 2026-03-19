# 用户管理系统 API 文档

## 项目概述
基于 Flask + SQLite 的用户管理系统后端 API，提供权限管理、用户管理和操作日志功能。

## 基础信息
- 服务地址: http://127.0.0.1:5000
- 数据格式: JSON
- 认证方式: JWT Bearer Token

## 测试账号
- 管理员: admin / admin123
- 普通用户: test / test123

## API 接口列表

### 1. 认证接口

#### 用户登录
```
POST /api/auth/login
Content-Type: application/json

请求体:
{
    "username": "admin",
    "password": "admin123"
}

响应:
{
    "message": "登录成功",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": { 用户信息对象 }
}
```

#### 获取当前用户信息
```
GET /api/auth/profile
Authorization: Bearer <access_token>

响应:
{
    "data": { 用户信息对象 }
}
```

---

### 2. 权限管理接口

#### 获取权限列表
```
GET /api/permissions
Authorization: Bearer <access_token>

查询参数:
- page: 页码 (默认: 1)
- per_page: 每页条数 (默认: 10)
- module: 模块筛选 (如: user, permission, role)
- keyword: 关键词搜索

响应:
{
    "data": [ 权限对象数组 ],
    "total": 总数,
    "page": 当前页,
    "per_page": 每页条数,
    "pages": 总页数
}
```

#### 创建权限
```
POST /api/permissions
Authorization: Bearer <access_token>
Content-Type: application/json

请求体:
{
    "name": "permission:create",
    "description": "创建权限",
    "module": "permission"
}

响应:
{
    "message": "权限创建成功",
    "data": { 权限对象 }
}
```

#### 获取单个权限
```
GET /api/permissions/<permission_id>
Authorization: Bearer <access_token>
```

#### 更新权限
```
PUT /api/permissions/<permission_id>
Authorization: Bearer <access_token>
Content-Type: application/json

请求体:
{
    "name": "permission:update",
    "description": "更新权限描述",
    "module": "permission"
}
```

#### 删除权限
```
DELETE /api/permissions/<permission_id>
Authorization: Bearer <access_token>
```

---

### 3. 角色管理接口

#### 获取角色列表
```
GET /api/roles
Authorization: Bearer <access_token>

查询参数:
- page: 页码
- per_page: 每页条数
- keyword: 关键词搜索
```

#### 创建角色
```
POST /api/roles
Authorization: Bearer <access_token>
Content-Type: application/json

请求体:
{
    "name": "editor",
    "description": "编辑角色",
    "is_active": true,
    "permission_ids": [1, 2, 3]  // 权限ID列表
}
```

#### 获取/更新/删除单个角色
```
GET    /api/roles/<role_id>
PUT    /api/roles/<role_id>
DELETE /api/roles/<role_id>
```

---

### 4. 用户管理接口

#### 获取用户列表
```
GET /api/users
Authorization: Bearer <access_token>

查询参数:
- page: 页码
- per_page: 每页条数
- keyword: 关键词搜索 (用户名/邮箱/姓名)
- is_active: 是否激活 (true/false)
```

#### 创建用户（注册）
```
POST /api/users
Content-Type: application/json

请求体:
{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "password123",
    "full_name": "新用户",
    "phone": "13800138000",
    "role_ids": [2]  // 角色ID列表
}
```

#### 获取/更新/删除单个用户
```
GET    /api/users/<user_id>
PUT    /api/users/<user_id>
DELETE /api/users/<user_id>
```

---

### 5. 操作日志接口

#### 获取操作日志列表
```
GET /api/logs
Authorization: Bearer <access_token>

查询参数:
- page: 页码
- per_page: 每页条数
- user_id: 用户ID筛选
- action: 操作类型筛选
- status: 状态筛选 (success/failed)
- start_date: 开始日期 (YYYY-MM-DD)
- end_date: 结束日期 (YYYY-MM-DD)
```

#### 获取单条日志详情
```
GET /api/logs/<log_id>
Authorization: Bearer <access_token>
```

---

## 数据对象示例

### 权限对象
```json
{
    "id": 1,
    "name": "user:view",
    "description": "查看用户",
    "module": "user",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
}
```

### 角色对象
```json
{
    "id": 1,
    "name": "admin",
    "description": "系统管理员",
    "is_active": true,
    "permissions": [ 权限对象数组 ],
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
}
```

### 用户对象
```json
{
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "full_name": "系统管理员",
    "phone": "13800138000",
    "avatar": null,
    "is_active": true,
    "last_login": "2024-01-01T00:00:00",
    "roles": [ 角色对象数组 ],
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
}
```

### 日志对象
```json
{
    "id": 1,
    "user_id": 1,
    "username": "admin",
    "action": "login",
    "description": "登录成功",
    "ip_address": "127.0.0.1",
    "user_agent": "Mozilla/5.0...",
    "status": "success",
    "created_at": "2024-01-01T00:00:00"
}
```

---

## 项目结构

```
├── app.py              # 应用入口
├── extensions.py       # 扩展初始化
├── models.py           # 数据模型
├── routes.py           # 路由定义
├── init_data.py        # 初始化数据脚本
├── .env                # 环境变量
└── user_management.db  # SQLite数据库文件
```
