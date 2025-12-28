# 基础镜像
FROM python:3.9-slim

# 安装YOLO11所需的系统依赖（新增，避免后续运行报错）
RUN apt update && apt install -y libgl1-mesa-glx libglib2.0-0 && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖清单
COPY requirements.txt .

# 升级pip（解决低版本pip安装问题）+ 安装Python依赖
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目所有文件（包括best.pt模型）
COPY . .

# 暴露Flask服务端口（Nginx反向代理指向5000）
EXPOSE 5000

# 启动Flask服务
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]