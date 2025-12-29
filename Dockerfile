# 基础镜像：改用阿里云的Python镜像（网络更优）
FROM registry.cn-hangzhou.aliyuncs.com/acs/python:3.9-slim

# ========== 彻底替换Debian源 + 优化网络参数 ==========
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye main contrib non-free" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security/ bullseye-security main contrib non-free" >> /etc/apt/sources.list && \
    # 增加网络超时参数，避免apt超时
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

# ========== 拆分pip升级：单独指定清华源，避免超时 ==========
# 升级pip（指定清华源 + 超时参数）
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=120 \
    --retries=3

# 复制依赖清单
COPY requirements.txt .

# ========== 安装Python依赖：优化顺序 + 国内镜像 ==========
# 1. 先安装torch（单独指定阿里云镜像，解决大依赖超时）
RUN pip install torch>=2.0.0 -i https://mirrors.aliyun.com/pypi/simple/ \
    --default-timeout=300 \
    --retries=3 \
    --no-cache-dir

# 2. 再安装其余依赖（清华源 + 超时 + 重试）
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=120 \
    --retries=3

# 复制项目所有文件（包括best.pt模型）
COPY . .

# 创建上传/结果目录
RUN mkdir -p /app/uploads /app/results

# 暴露正确端口
EXPOSE 8000

# 设置Flask环境变量 + 启动服务
ENV FLASK_APP=app.py
CMD ["flask", "run", "--host=0.0.0.0", "--port=8000"]