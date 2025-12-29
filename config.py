# 数据库配置
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",       # 替换为你的MySQL用户名
    "password": "123456", # 替换为你的MySQL密码
    "database": "yolo_detect"
}

# Redis配置
REDIS_CONFIG = {
    "host": "127.0.0.1",
    "port": 6379,
    "db": 0,
    "password": ""        # 无密码则留空，有则填写
}

# 豆包API配置
DOUBAO_CONFIG = {
    "api_key": "api-key-20251226210534",
    "secret_key": "078cb0fc-1f65-479f-80f3-10ce1e7c8a90",
    "token_expire": 3600  # Token缓存1小时
}

# 模型路径（沿用你的路径）
MODEL_PATH = r"C:\Users\1\yolov10\yolo11_web\best.pt"

# 路径配置
UPLOAD_FOLDER = "static/uploads"
RESULT_FOLDER = "static/results"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp"}