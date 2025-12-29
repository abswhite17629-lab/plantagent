# config.py - 适配Linux/容器环境的配置文件
import os

# ===================== 路径配置（容器内路径） =====================
UPLOAD_FOLDER = "/app/uploads"       # 上传文件目录（替换原/tmp，更规范）
RESULT_FOLDER = "/app/results"       # 结果文件目录
MODEL_PATH = "yolo11n.pt"            # 改为YOLO11官方模型（自动下载）
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}  # 允许的文件格式

# ===================== MySQL配置（按需启用，注释则不使用） =====================
MYSQL_CONFIG = {
    "host": "mysql-service.mysql.svc.cluster.local",
    "user": "root",
    "password": "123456",
    "database": "yolo_detect",  # 需提前创建数据库
    "charset": "utf8mb4"
}

# ===================== Redis配置（按需启用，注释则不使用） =====================
REDIS_CONFIG = {
    "host": "redis-service.redis.svc.cluster.local",
    "port": 6379,
    "password": "123456",
    "db": 0,
    "decode_responses": True
}

# ===================== 豆包AI配置（补充完整，替换为真实密钥） =====================
DOUBAO_CONFIG = {
    "api_key": "078cb0fc-1f65-479f-80f3-10ce1e7c8a90",       # 替换为真实密钥
    "secret_key": "", # 若不需要可留空
    "api_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",  # 豆包API地址
    "model": "doubao-1-5-lite-32k-250115",        # 豆包模型版本
    "token_expire": 3600,               # Token过期时间（1小时）
    "timeout": 20                       # API调用超时时间
}

# ===================== Flask配置 =====================
FLASK_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": False
}