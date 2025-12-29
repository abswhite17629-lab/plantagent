# 基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 换阿里云源，加速依赖安装
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# ========== 新增1：赋予/app目录读写权限（关键！） ==========
RUN mkdir -p /app/uploads /app/results && chmod -R 777 /app

# 复制依赖文件并安装（包含MySQL/Redis/豆包依赖）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有代码到镜像（config.py/app.py都会被复制）
COPY . .

# 环境变量：禁用GPU+日志优化
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=-1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "app.py"]