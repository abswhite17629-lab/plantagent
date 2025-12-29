# 原基础镜像（保留）
FROM python:3.9-slim

# 新增：安装YOLO依赖的系统库（关键！）
RUN apt update && apt install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*  # 清理apt缓存，减小镜像体积

# 原有配置（保留）
WORKDIR /app
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
RUN mkdir -p /app/uploads /app/results && chmod -R 777 /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=-1
EXPOSE 8000
CMD ["python", "app.py"]