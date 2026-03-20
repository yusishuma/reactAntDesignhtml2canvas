from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

# EmailStr 需要 email-validator，这里使用正则验证
from pydantic import field_validator


# ==================== 通用响应模型 ====================

class ResponseModel(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[dict] = None


class PaginatedResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: dict


# ==================== 认证相关 ====================

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    username: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# ==================== 用户相关 ====================

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=100)
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_active: bool = True
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email address')
        return v


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)
    role_ids: Optional[List[int]] = []


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    avatar: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    role_ids: Optional[List[int]] = None
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email address')
        return v


class RoleSimple(BaseModel):
    id: int
    name: str
    code: str
    
    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    id: int
    avatar: Optional[str] = None
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    roles: List[RoleSimple] = []
    
    model_config = ConfigDict(from_attributes=True)


class UserSimple(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 角色相关 ====================

class RoleBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    code: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    is_active: bool = True


class RoleCreate(RoleBase):
    permission_ids: Optional[List[int]] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=50)
    code: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    permission_ids: Optional[List[int]] = None


class PermissionSimple(BaseModel):
    id: int
    name: str
    code: str
    resource: str
    action: str
    
    model_config = ConfigDict(from_attributes=True)


class RoleResponse(RoleBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    permissions: List[PermissionSimple] = []
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 权限相关 ====================

class PermissionBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    code: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    resource: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=50)
    is_active: bool = True


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=50)
    code: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    resource: Optional[str] = Field(None, min_length=1, max_length=50)
    action: Optional[str] = Field(None, min_length=1, max_length=50)
    is_active: Optional[bool] = None


class PermissionResponse(PermissionBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 日志相关 ====================

class LogAction(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    EXPORT = "export"
    IMPORT = "import"


class LogStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class UserLogBase(BaseModel):
    action: LogAction
    resource: Optional[str] = None
    resource_id: Optional[int] = None
    description: Optional[str] = None
    status: LogStatus = LogStatus.SUCCESS


class UserLogCreate(UserLogBase):
    user_id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[str] = None


class UserLogResponse(UserLogBase):
    id: int
    user_id: int
    user: UserSimple
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserLogQuery(BaseModel):
    user_id: Optional[int] = None
    action: Optional[LogAction] = None
    resource: Optional[str] = None
    status: Optional[LogStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ==================== 分页查询参数 ====================

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    keyword: Optional[str] = None
