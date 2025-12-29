# 基础镜像（保留python:3.9-slim-bullseye）
FROM python:3.9-slim-bullseye

# ========== 修复：仅保留阿里云稳定源（删除backports） ==========
RUN echo "deb http://mirrors.aliyun.com/debian/ bullseye main non-free contrib" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib" >> /etc/apt/sources.list

# ========== 精简安装必需系统库（无依赖问题） ==========
RUN apt update && apt install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && apt clean && rm -rf /var/lib/apt/lists/*  # 清理缓存，避免体积过大

# ========== 原有配置（保留） ==========
WORKDIR /app
# 阿里云pip源加速Python包安装
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
# 创建目录并赋权（容器内路径）
RUN mkdir -p /app/uploads /app/results && chmod -R 777 /app
# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# 复制项目代码
COPY . .
# 环境变量配置
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=-1
# 暴露端口
EXPOSE 8000
# 启动命令
CMD ["python", "app.py"]