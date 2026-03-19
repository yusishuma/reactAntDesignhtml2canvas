from app.routers.users import router as users_router
from app.routers.permissions import router as permissions_router
from app.routers.logs import router as logs_router

__all__ = ["users_router", "permissions_router", "logs_router"]
