# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO11检测服务（容器版）
集成：豆包AI分析 + MySQL自动建库/存储 + Redis缓存
适配Linux/容器环境，容错设计：MySQL/Redis/豆包异常不影响核心检测功能
"""
import os
import time
import torch
import requests
import pymysql
import redis
from flask import Flask, request, jsonify
from datetime import datetime

# 导入配置文件（需确保config.py在同目录）
import config

# ===================== 基础环境初始化 =====================
# 强制禁用GPU，避免容器/无GPU环境兼容问题
torch.cuda.is_available = lambda: False

# 初始化Flask应用
app = Flask(__name__)

# ===================== 目录初始化（容器环境必备） =====================
def init_folders():
    """初始化上传/结果目录，避免容器内路径不存在报错"""
    for folder in [config.UPLOAD_FOLDER, config.RESULT_FOLDER]:
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
                print(f"✅ 成功创建目录：{folder}")
            except Exception as e:
                print(f"⚠️ 创建目录失败（不影响核心功能）：{folder} - {str(e)}")

# ===================== 文件格式校验 =====================
def allowed_file(filename):
    """校验上传文件格式是否符合要求"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

# ===================== MySQL模块（自动建库+存储，可选启用） =====================
mysql_conn = None  # 全局MySQL连接对象

def init_mysql():
    """
    初始化MySQL：
    1. 先连接服务器创建数据库（不存在则创建）
    2. 再连接数据库创建检测日志表
    3. 失败仅告警，不影响核心功能
    """
    global mysql_conn
    try:
        # 1. 校验MySQL基础配置（host/user/password）
        basic_config = {
            "host": config.MYSQL_CONFIG.get("host"),
            "user": config.MYSQL_CONFIG.get("user"),
            "password": config.MYSQL_CONFIG.get("password"),
            "charset": config.MYSQL_CONFIG.get("charset", "utf8mb4")
        }
        if not all([basic_config["host"], basic_config["user"]]):
            print("⚠️ MySQL基础配置不完整（host/user缺失），跳过MySQL初始化")
            return False
        
        # 2. 连接MySQL服务器（不指定数据库），创建yolo_detect数据库
        temp_conn = pymysql.connect(**basic_config)
        db_name = config.MYSQL_CONFIG["database"]
        create_db_sql = f"CREATE DATABASE IF NOT EXISTS {db_name} DEFAULT CHARACTER SET utf8mb4;"
        with temp_conn.cursor() as cursor:
            cursor.execute(create_db_sql)
        temp_conn.commit()
        temp_conn.close()
        print(f"✅ MySQL数据库 '{db_name}' 已创建/存在")

        # 3. 连接新建的数据库，创建检测日志表
        mysql_conn = pymysql.connect(**config.MYSQL_CONFIG)
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS detect_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            filename VARCHAR(255) NOT NULL COMMENT '上传文件名',
            detections TEXT NOT NULL COMMENT '检测结果JSON字符串',
            ai_analysis TEXT COMMENT '豆包AI分析结果',
            create_time DATETIME NOT NULL COMMENT '检测时间',
            file_path VARCHAR(255) COMMENT '文件存储路径'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='YOLO检测日志表';
        """
        with mysql_conn.cursor() as cursor:
            cursor.execute(create_table_sql)
        mysql_conn.commit()
        print("✅ MySQL检测日志表 'detect_log' 已创建/存在")
        return True
    except Exception as e:
        print(f"⚠️ MySQL初始化失败（不影响核心功能）：{str(e)}")
        mysql_conn = None
        return False

def save_to_mysql(filename, detections, ai_analysis, file_path):
    """保存检测结果到MySQL，失败仅打印日志"""
    if not mysql_conn:
        return False
    try:
        insert_sql = """
        INSERT INTO detect_log (filename, detections, ai_analysis, create_time, file_path)
        VALUES (%s, %s, %s, %s, %s);
        """
        # 转换检测结果为字符串存储（JSON格式兼容）
        detections_str = str(detections)
        with mysql_conn.cursor() as cursor:
            cursor.execute(insert_sql, (
                filename, detections_str, ai_analysis,
                datetime.now(), file_path
            ))
        mysql_conn.commit()
        print(f"✅ 检测记录已保存到MySQL：{filename}")
        return True
    except Exception as e:
        print(f"⚠️ 保存MySQL失败（不影响核心功能）：{str(e)}")
        return False

# ===================== Redis模块（缓存，可选启用） =====================
redis_client = None  # 全局Redis客户端对象

def init_redis():
    """初始化Redis客户端，失败仅告警，不影响核心功能"""
    global redis_client
    try:
        # 校验Redis基础配置
        if not config.REDIS_CONFIG.get("host"):
            print("⚠️ Redis配置不完整（host缺失），跳过Redis初始化")
            return False
        
        # 建立连接并测试
        redis_client = redis.Redis(**config.REDIS_CONFIG)
        redis_client.ping()  # 测试连接
        print("✅ Redis初始化成功")
        return True
    except Exception as e:
        print(f"⚠️ Redis初始化失败（不影响核心功能）：{str(e)}")
        redis_client = None
        return False

def save_to_redis(filename, detections, ai_analysis, expire=3600):
    """缓存检测结果到Redis（1小时过期），失败仅打印日志"""
    if not redis_client:
        return False
    try:
        # 构造唯一缓存Key（文件名+时间戳，避免重复）
        cache_key = f"yolo:detect:{filename}:{int(time.time())}"
        # 构造缓存值（哈希类型，便于查询）
        cache_value = {
            "detections": str(detections),
            "ai_analysis": ai_analysis,
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "filename": filename
        }
        # 保存到Redis并设置过期时间
        redis_client.hmset(cache_key, cache_value)
        redis_client.expire(cache_key, expire)
        print(f"✅ 检测记录已缓存到Redis：{cache_key}（过期时间{expire}秒）")
        return True
    except Exception as e:
        print(f"⚠️ 保存Redis失败（不影响核心功能）：{str(e)}")
        return False

# ===================== 豆包AI模块（分析检测结果） =====================
def call_doubao_ai(detections):
    """调用豆包大模型，生成检测结果的自然语言分析，失败返回兜底提示"""
    # 兜底提示（AI调用失败时返回）
    fallback_msg = "豆包AI分析暂不可用，可直接查看检测结果"
    
    # 校验豆包API Key是否配置
    if not config.DOUBAO_CONFIG["api_key"] or config.DOUBAO_CONFIG["api_key"] == "你的豆包API Key":
        print("❌ 未配置有效豆包API Key，跳过AI分析")
        return fallback_msg

    # 构造豆包AI提示词（简洁易懂，适配检测结果）
    prompt = f"""
    请分析以下YOLO11目标检测结果，生成100字以内的自然语言描述：
    检测结果：{detections}
    要求：
    1. 说明检测到的目标类型和数量；
    2. 语言通俗，无技术术语；
    3. 简洁明了，重点突出。
    """

    try:
        # 调用豆包API
        response = requests.post(
            config.DOUBAO_CONFIG["api_url"],
            headers={
                "Authorization": f"Bearer {config.DOUBAO_CONFIG['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": config.DOUBAO_CONFIG["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.6,  # 随机性：0-1，越小越稳定
                "max_tokens": 150     # 最大返回字数
            },
            timeout=config.DOUBAO_CONFIG["timeout"]
        )

        # 解析返回结果
        if response.status_code == 200:
            result = response.json()
            ai_analysis = result["choices"][0]["message"]["content"].strip()
            return ai_analysis
        else:
            print(f"❌ 豆包API调用失败：{response.status_code} - {response.text}")
            return fallback_msg
    except Exception as e:
        print(f"❌ 豆包AI调用异常：{str(e)}")
        return fallback_msg

# ===================== YOLO11模型加载 =====================
model = None  # 全局YOLO模型对象

try:
    from ultralytics import YOLO
    # 从配置文件读取模型路径（官方yolo11n.pt，自动下载）
    model = YOLO(config.MODEL_PATH)
    print(f"✅ YOLO11模型加载成功（模型路径：{config.MODEL_PATH}）")
except Exception as e:
    print(f"❌ YOLO11模型加载失败：{str(e)}")

# ===================== Flask路由 =====================
@app.route('/')
def index():
    """主页：提供图片上传表单"""
    return """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>YOLO11检测服务（容器版）</title>
        <style>
            body {max-width: 800px; margin: 20px auto; padding: 0 20px; font-family: Arial;}
            h1 {color: #2c3e50;}
            .form-box {margin-top: 20px; padding: 20px; border: 1px solid #eee; border-radius: 8px;}
            input[type=file] {margin: 10px 0; padding: 8px;}
            button {padding: 8px 20px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;}
            button:hover {background: #2980b9;}
        </style>
    </head>
    <body>
        <h1>YOLO11目标检测服务</h1>
        <p>集成豆包AI分析 + MySQL存储 + Redis缓存（容器版）</p>
        <div class="form-box">
            <form action="/detect" method="post" enctype="multipart/form-data">
                <input type="file" name="image" accept="image/*" required>
                <button type="submit">上传图片并检测</button>
            </form>
        </div>
        <p><a href="/history">查看检测历史记录</a></p>
    </body>
    </html>
    """

@app.route('/detect', methods=['POST'])
def detect():
    """核心检测接口：接收图片→YOLO检测→豆包AI分析→MySQL/Redis存储"""
    # 模型未加载时返回错误
    if not model:
        return jsonify({"code": 500, "msg": "YOLO11模型未加载，请检查模型配置"}), 500

    try:
        # 1. 校验上传文件
        if 'image' not in request.files:
            return jsonify({"code": 400, "msg": "未上传图片文件"}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({"code": 400, "msg": "图片文件名不能为空"}), 400
        
        # 2. 校验文件格式
        if not (file and allowed_file(file.filename)):
            return jsonify({
                "code": 400,
                "msg": f"不支持的文件格式，仅允许：{','.join(config.ALLOWED_EXTENSIONS)}"
            }), 400

        # 3. 保存图片到容器指定目录
        filename = os.path.basename(file.filename)
        img_path = os.path.join(config.UPLOAD_FOLDER, filename)
        file.save(img_path)
        print(f"✅ 上传图片已保存：{img_path}")

        # 4. 执行YOLO11检测
        results = model(img_path)
        
        # 5. 解析检测结果
        detections = []
        for r in results:
            for box in r.boxes:
                detections.append({
                    "类别": model.names[int(box.cls)],
                    "置信度": round(float(box.conf), 2),
                    "坐标": [round(x, 2) for x in box.xyxy.tolist()[0]]  # [x1,y1,x2,y2]
                })

        # 6. 调用豆包AI分析检测结果
        ai_analysis = call_doubao_ai(detections)

        # 7. 保存结果到MySQL和Redis（失败不影响返回）
        save_to_mysql(filename, detections, ai_analysis, img_path)
        save_to_redis(filename, detections, ai_analysis)

        # 8. 返回最终结果
        return jsonify({
            "code": 200,
            "msg": "检测成功（已尝试保存到MySQL/Redis）",
            "检测结果": detections,
            "豆包AI分析": ai_analysis,
            "文件名称": filename,
            "文件路径": img_path
        }), 200

    except Exception as e:
        # 捕获所有异常，返回友好提示
        print(f"❌ 检测接口异常：{str(e)}")
        return jsonify({"code": 500, "msg": f"检测失败：{str(e)}"}), 500

@app.route('/history', methods=['GET'])
def get_history():
    """查询MySQL中的检测历史记录（最近100条）"""
    # MySQL未初始化时返回错误
    if not mysql_conn:
        return jsonify({"code": 500, "msg": "MySQL未初始化/连接失败，无法查询历史记录"}), 500
    
    try:
        # 查询最近100条记录
        query_sql = """
        SELECT filename, detections, ai_analysis, create_time, file_path
        FROM detect_log
        ORDER BY create_time DESC
        LIMIT 100;
        """
        with mysql_conn.cursor() as cursor:
            cursor.execute(query_sql)
            results = cursor.fetchall()
        
        # 格式化结果（转换为易读的JSON格式）
        history_list = []
        for row in results:
            history_list.append({
                "文件名": row[0],
                "检测结果": eval(row[1]),  # 还原为列表（仅信任内部数据，生产环境建议用json.loads）
                "豆包AI分析": row[2],
                "检测时间": row[3].strftime("%Y-%m-%d %H:%M:%S"),
                "文件路径": row[4]
            })
        
        return jsonify({
            "code": 200,
            "msg": "历史记录查询成功",
            "记录总数": len(history_list),
            "历史记录": history_list
        }), 200
    except Exception as e:
        print(f"❌ 历史查询接口异常：{str(e)}")
        return jsonify({"code": 500, "msg": f"查询历史记录失败：{str(e)}"}), 500

# ===================== 程序入口 =====================
if __name__ == '__main__':
    # 1. 初始化容器目录
    init_folders()
    # 2. 初始化MySQL（可选）
    init_mysql()
    # 3. 初始化Redis（可选）
    init_redis()
    # 4. 启动Flask服务（从配置文件读取参数）
    print(f"🚀 启动YOLO11检测服务：http://{config.FLASK_CONFIG['host']}:{config.FLASK_CONFIG['port']}")
    app.run(
        host=config.FLASK_CONFIG["host"],
        port=config.FLASK_CONFIG["port"],
        debug=config.FLASK_CONFIG["debug"]
    )