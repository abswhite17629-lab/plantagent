# 基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制依赖清单
COPY requirements.txt .

# 安装依赖（国内源加速，包含YOLO11依赖）
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目所有文件（包括best.pt模型）
COPY . .

# 暴露Flask服务端口（Nginx反向代理指向5000）
EXPOSE 5000

# 启动Flask服务
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]