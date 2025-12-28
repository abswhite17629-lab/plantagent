import os
import time
import json
import requests
import pymysql
import redis
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
from ultralytics import YOLO
import cv2
from PIL import Image
from config import *

# 初始化Flask应用
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULT_FOLDER'] = RESULT_FOLDER

# 创建文件夹（若不存在）
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)


# 初始化MySQL连接
def get_mysql_conn():
    conn = pymysql.connect(**MYSQL_CONFIG)
    conn.autocommit(True)
    return conn


# 初始化Redis连接
redis_client = redis.Redis(**REDIS_CONFIG)

# 初始化YOLO11模型
model = YOLO(MODEL_PATH)


# ==================== 数据库初始化（首次运行执行） ====================
def init_mysql():
    conn = get_mysql_conn()
    cursor = conn.cursor()
    # 创建检测记录表格
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS detect_records (
        id INT AUTO_INCREMENT PRIMARY KEY,
        filename VARCHAR(255) NOT NULL,
        upload_time DATETIME NOT NULL,
        img_path VARCHAR(255) NOT NULL,
        result_img_path VARCHAR(255) NOT NULL,
        detect_info TEXT,
        ai_analysis TEXT,
        total_targets INT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    cursor.execute(create_table_sql)
    conn.close()
    print("✅ MySQL表初始化完成")


# 首次运行调用初始化
init_mysql()


# ==================== 工具函数 ====================
# 检查文件后缀是否允许
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# 获取豆包Token（Redis缓存）
def get_doubao_token():
    # 先从Redis取缓存
    token = redis_client.get("doubao_token")
    if token:
        return token.decode('utf-8')
    # 缓存未命中，调用API获取
    url = "https://www.doubao.com/open/api/v1/auth/token"
    headers = {"Content-Type": "application/json"}
    data = {
        "api_key": DOUBAO_CONFIG["api_key"],
        "secret_key": DOUBAO_CONFIG["secret_key"]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        token = response.json()["data"]["access_token"]
        # 缓存Token（设置过期时间）
        redis_client.setex("doubao_token", DOUBAO_CONFIG["token_expire"], token)
        return token
    except Exception as e:
        print(f"❌ 获取豆包Token失败：{e}")
        return None


# 豆包AI分析
def analyze_with_doubao(detect_info):
    token = get_doubao_token()
    if not token:
        return "❌ 无法连接豆包大模型，请检查API密钥"

    prompt = f"""
    你是专业的YOLO11目标检测分析助手，分析以下结果：
    1. 列出检测到的目标类别及数量；
    2. 说明目标位置分布；
    3. 判断图片场景；
    4. 补充1-2个关键细节。
    检测结果：{detect_info}
    要求：分点说明，语言通俗。
    """
    url = "https://www.doubao.com/open/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = {
        "model": "doubao-lite",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ 分析失败：{str(e)}"


# ==================== 路由（页面+接口） ====================
# 首页（上传图片）
@app.route('/')
def index():
    return render_template('index.html')


# 上传图片并检测
@app.route('/detect', methods=['POST'])
def detect():
    # 检查是否有文件上传
    if 'file' not in request.files:
        return "❌ 未选择文件", 400
    file = request.files['file']
    if file.filename == '':
        return "❌ 文件名为空", 400
    if file and allowed_file(file.filename):
        # 生成唯一文件名（避免重复）
        timestamp = int(time.time())
        filename = f"{timestamp}_{file.filename}"
        img_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(img_path)

        # 执行YOLO11检测
        results = model(img_path)
        result = results[0]

        # 整理检测信息
        detect_info = {
            "resolution": f"{result.orig_shape[1]}×{result.orig_shape[0]}",
            "total_targets": len(result.boxes),
            "targets": []
        }
        for box in result.boxes:
            cls_name = result.names[int(box.cls)]
            confidence = round(float(box.conf), 2)
            x1, y1, x2, y2 = [round(x) for x in box.xyxy.tolist()[0]]
            detect_info["targets"].append({
                "class": cls_name,
                "confidence": confidence,
                "position": f"左上({x1},{y1}) 右下({x2},{y2})"
            })
        detect_info_str = json.dumps(detect_info, ensure_ascii=False)

        # 生成检测结果图片
        result_img = result.plot()
        result_img = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
        result_img_path = os.path.join(app.config['RESULT_FOLDER'], filename)
        Image.fromarray(result_img).save(result_img_path)

        # 调用豆包AI分析
        ai_analysis = analyze_with_doubao(detect_info_str)

        # 保存到MySQL
        conn = get_mysql_conn()
        cursor = conn.cursor()
        insert_sql = """
        INSERT INTO detect_records (filename, upload_time, img_path, result_img_path, detect_info, ai_analysis, total_targets)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_sql, (
            file.filename,
            datetime.now(),
            img_path,
            result_img_path,
            detect_info_str,
            ai_analysis,
            len(result.boxes)
        ))
        record_id = cursor.lastrowid
        conn.close()

        # 跳转到结果页
        return redirect(url_for('result', record_id=record_id))
    else:
        return "❌ 不支持的文件格式", 400


# 检测结果页
@app.route('/result/<int:record_id>')
def result(record_id):
    conn = get_mysql_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM detect_records WHERE id = %s", (record_id,))
    record = cursor.fetchone()
    conn.close()
    if not record:
        return "❌ 记录不存在", 404
    # 解析检测信息
    record['detect_info'] = json.loads(record['detect_info'])
    return render_template('result.html', record=record)


# 历史记录页
@app.route('/history')
def history():
    conn = get_mysql_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM detect_records ORDER BY upload_time DESC")
    records = cursor.fetchall()
    conn.close()
    return render_template('history.html', records=records)


# ==================== 启动程序 ====================
if __name__ == '__main__':
    # 本地调试用，生产环境用Gunicorn+Nginx
    app.run(host='0.0.0.0', port=5000, debug=True)