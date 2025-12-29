# 换回官方Python基础镜像（稳定可用）
FROM python:3.9-slim

# ========== 替换Debian源 + 网络优化 ==========
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye main contrib non-free" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security/ bullseye-security main contrib non-free" >> /etc/apt/sources.list && \
    # 增加apt超时参数，避免网络波动
    apt -o Acquire::Timeout=60 update && \
    apt install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
        libopencv-core4.5 \
        libopencv-imgproc4.5 && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 设置工作目录
WORKDIR /app

# ========== 升级pip：指定清华源 + 超时 + 重试 ==========
RUN pip install --upgrade pip \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=120 \
    --retries=3 \
    --no-cache-dir

# 复制依赖清单
COPY requirements.txt .

# ========== 单独安装torch（阿里云源，解决大依赖超时） ==========
RUN pip install torch>=2.0.0 \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --default-timeout=300 \
    --retries=3 \
    --no-cache-dir

# ========== 安装其余依赖（清华源 + 超时 + 重试） ==========
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=120 \
    --retries=3

# 复制项目文件（含best.pt）
COPY . .

# 创建上传/结果目录
RUN mkdir -p /app/uploads /app/results

# 暴露端口
EXPOSE 8000

# 设置Flask环境变量 + 启动服务
ENV FLASK_APP=app.py
CMD ["flask", "run", "--host=0.0.0.0", "--port=8000"]