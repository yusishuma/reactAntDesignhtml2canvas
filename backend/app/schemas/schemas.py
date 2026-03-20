from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr


class PermissionBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool = True


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PermissionResponse(PermissionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str
    permission_ids: Optional[List[int]] = []


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    permission_ids: Optional[List[int]] = None


class UserResponse(UserBase):
    id: int
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    permissions: List[PermissionResponse] = []

    class Config:
        from_attributes = True


class UserLogBase(BaseModel):
    action: str
    description: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_url: Optional[str] = None
    request_method: Optional[str] = None
    status_code: Optional[int] = None


class UserLogCreate(UserLogBase):
    user_id: int


class UserLogResponse(UserLogBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List
