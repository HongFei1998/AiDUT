"""
AI手机助手 - 启动文件
"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 50)
    print("🤖 AI手机助手启动中...")
    print("=" * 50)
    print("📌 访问地址: http://localhost:5000")
    print("📌 请确保已连接Android设备并开启USB调试")
    print("=" * 50)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=app.config.get('DEBUG', True)
    )

