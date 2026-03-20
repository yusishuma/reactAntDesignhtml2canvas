from flask import Flask, jsonify
from datetime import timedelta
import os
import logging
from logging.handlers import RotatingFileHandler
from extensions import db, bcrypt, jwt, api

def setup_logging(app):
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10240000,
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Application startup')

def create_app():
    app = Flask(__name__)

    # 配置
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///instance/user_management.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

    # 设置日志
    setup_logging(app)

    # 初始化扩展
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    api.init_app(app)

    # 健康检查端点
    @app.route('/health')
    def health_check():
        try:
            # 检查数据库连接
            db.session.execute('SELECT 1')
            return jsonify({
                'status': 'healthy',
                'message': 'Application is running normally',
                'timestamp': os.times()
            }), 200
        except Exception as e:
            app.logger.error(f'Health check failed: {str(e)}')
            return jsonify({
                'status': 'unhealthy',
                'message': str(e)
            }), 500

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
