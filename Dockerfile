# 基础镜像
FROM python:3.9-slim

# ========== 彻底替换Debian源：重写sources.list ==========
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye main contrib non-free" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security/ bullseye-security main contrib non-free" >> /etc/apt/sources.list && \
    # 升级apt + 只装YOLO11 CPU运行必需的最小依赖（大幅减少下载量）
    apt update && \
    apt install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
        libopencv-core4.5 \
        libopencv-imgproc4.5 && \
    # 强制清理缓存，减小镜像体积
    apt clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 设置工作目录
WORKDIR /app

# 复制依赖清单（确保requirements.txt包含所有必要包）
COPY requirements.txt .

# 升级pip + 安装Python依赖（国内PyPI源，避免超时）
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目所有文件（包括best.pt模型、templates模板、app.py等）
COPY . .

# 关键：创建app.py需要的上传/结果目录（避免FileNotFoundError）
RUN mkdir -p /app/uploads /app/results

# 暴露正确的端口（匹配app.py的8000端口）
EXPOSE 8000

# 设置Flask环境变量 + 启动服务（适配app.py入口）
ENV FLASK_APP=app.py
CMD ["flask", "run", "--host=0.0.0.0", "--port=8000"]

# 备选启动方式（如果flask run有问题，可改用python直接启动）
# CMD ["python", "app.py"]