from flask import Flask
from datetime import timedelta
import os
from extensions import db, bcrypt, jwt, api

def create_app():
    app = Flask(__name__)

    # 配置
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user_management.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

    # 初始化扩展
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    api.init_app(app)

    # 导入模型和路由
    from models import Permission, Role, User, UserLog
    from routes import initialize_routes
    initialize_routes(api)

    # 创建数据库表
    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
