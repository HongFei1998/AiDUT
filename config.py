import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


class Config:
    """应用配置"""
    
    # Flask配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # 大模型配置
    LLM_API_KEY = os.getenv('LLM_API_KEY', '')
    LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4o')
    
    # 设备配置
    DEVICE_SERIAL = os.getenv('DEVICE_SERIAL', '')

