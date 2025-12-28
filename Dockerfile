# 基础镜像（根据你的Python版本调整）
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制项目依赖文件（如果有requirements.txt）
COPY requirements.txt .

# 安装依赖（如果没有requirements.txt，可注释这行）
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目所有文件到工作目录
COPY . .

# 暴露端口（根据你的项目调整，比如Flask/Django常用8000）
EXPOSE 8000

# 启动命令（根据你的项目入口文件调整，比如app.py）
CMD ["python", "app.py"]
