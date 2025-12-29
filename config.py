# config.py - 适配Linux/容器环境的配置文件
import os

# 路径配置（容器内路径）
UPLOAD_FOLDER = "/app/uploads"       # 上传文件目录
RESULT_FOLDER = "/app/results"       # 结果文件目录
MODEL_PATH = "./best.pt"             # YOLO模型文件（项目根目录）
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}  # 允许的文件格式

# MySQL配置（按需修改，先注释或填真实信息）
MYSQL_CONFIG = {
    "host": "mysql-service.mysql.svc.cluster.local",
    "user": "root",
    "password": "123456",
    "database": "yolo_detect",  # 需提前创建数据库
    "charset": "utf8mb4"
}

# Redis配置（按需修改，先注释或填真实信息）
REDIS_CONFIG = {
    "host": "redis-service.redis.svc.cluster.local",
    "port": 6379,
    "password": "123456",
    "db": 0,
    "decode_responses": True
}

# 豆包AI配置（替换为你的真实密钥）
DOUBAO_CONFIG = {
    "api_key": "你的豆包API Key",
    "secret_key": "你的豆包Secret Key",
    "token_expire": 3600  # Token过期时间（1小时）
}