# 基础镜像（保留python:3.9-slim，bullseye版本）
FROM python:3.9-slim-bullseye

# ========== 关键：替换为阿里云Debian国内源 ==========
RUN echo "deb http://mirrors.aliyun.com/debian/ bullseye main non-free contrib" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bullseye-backports main non-free contrib" >> /etc/apt/sources.list

# ========== 精简安装必需的系统库（仅装libGL相关，减少下载） ==========
RUN apt update && apt install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && apt clean && rm -rf /var/lib/apt/lists/*  # 强制清理缓存，减小镜像体积

# ========== 原有配置（保留） ==========
WORKDIR /app
# 替换pip源为阿里云，加速Python包安装
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
# 创建目录并赋权
RUN mkdir -p /app/uploads /app/results && chmod -R 777 /app
# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# 复制代码
COPY . .
# 环境变量
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=-1
# 暴露端口
EXPOSE 8000
# 启动命令
CMD ["python", "app.py"]