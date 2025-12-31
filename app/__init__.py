from flask import Flask
from flask_cors import CORS


def create_app():
    """创建Flask应用"""
    app = Flask(__name__)
    CORS(app)
    
    # 加载配置
    app.config.from_object('config.Config')
    
    # 注册蓝图
    from app.routes.device import device_bp
    from app.routes.chat import chat_bp
    
    app.register_blueprint(device_bp, url_prefix='/api/device')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    
    # 注册主页路由
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)
    
    return app

