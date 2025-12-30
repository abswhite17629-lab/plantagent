# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO11检测服务（容器版）
集成：豆包AI分析 + MySQL自动建库/存储 + Redis缓存
适配Linux/容器环境，容错设计：MySQL/Redis/豆包异常不影响核心检测功能
支持：纯文字提问、纯图片检测、文字+图片混合交互
"""
import os
import time
import torch
import requests
import pymysql
import redis
from flask import Flask, request, jsonify, render_template
from datetime import datetime

# 导入配置文件（需确保config.py在同目录）
import config

# ===================== 基础环境初始化 =====================
# 强制禁用GPU，避免容器/无GPU环境兼容问题
torch.cuda.is_available = lambda: False

# 初始化Flask应用（指定模板/静态文件目录，适配你的项目结构）
app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'),  # 模板目录
            static_folder=os.path.join(os.path.dirname(__file__), 'static'))       # 静态文件目录

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
    1. 自动创建数据库/表（filename允许为空，解决1048错误）；
    2. 自动检查并补全缺失的question字段（解决1054错误）；
    3. 自动修复filename的非空约束（解决纯文字提问保存失败）；
    4. 兼容MySQL 8.0语法，容错设计。
    """
    global mysql_conn
    try:
        # 1. 基础配置（补充端口+超时）
        basic_config = {
            "host": config.MYSQL_CONFIG.get("host"),
            "port": config.MYSQL_CONFIG.get("port", 3306),
            "user": config.MYSQL_CONFIG.get("user"),
            "password": config.MYSQL_CONFIG.get("password"),
            "charset": config.MYSQL_CONFIG.get("charset", "utf8mb4"),
            "connect_timeout": 10
        }
        if not all([basic_config["host"], basic_config["user"], basic_config["port"]]):
            print("⚠️ MySQL基础配置不完整，跳过MySQL初始化")
            return False
        
        # 2. 创建数据库（如果不存在）
        temp_conn = pymysql.connect(**basic_config)
        db_name = config.MYSQL_CONFIG["database"]
        create_db_sql = f"CREATE DATABASE IF NOT EXISTS {db_name} DEFAULT CHARACTER SET utf8mb4;"
        with temp_conn.cursor() as cursor:
            cursor.execute(create_db_sql)
        temp_conn.commit()
        temp_conn.close()
        print(f"✅ MySQL数据库 '{db_name}' 已创建/存在")

        # 3. 连接数据库并创建表（filename允许为空）
        mysql_config_full = config.MYSQL_CONFIG.copy()
        mysql_config_full["connect_timeout"] = 10
        mysql_conn = pymysql.connect(**mysql_config_full)
        
        # 3.1 创建表的SQL（关键：filename去掉NOT NULL，允许为空）
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS detect_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            filename VARCHAR(255) COMMENT '上传文件名',  -- 去掉NOT NULL，允许为空
            detections TEXT COMMENT '检测结果JSON字符串', -- 去掉NOT NULL，纯文字提问时为空
            ai_analysis TEXT COMMENT '豆包AI分析结果',
            question TEXT COMMENT '用户提问文本',
            create_time DATETIME NOT NULL COMMENT '检测时间',
            file_path VARCHAR(255) COMMENT '文件存储路径'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='YOLO检测日志表';
        """
        with mysql_conn.cursor() as cursor:
            cursor.execute(create_table_sql)
        
        # 3.2 修复1：自动检查并添加缺失的question字段（解决1054错误）
        with mysql_conn.cursor() as cursor:
            check_column_sql = f"""
            SELECT COLUMN_NAME 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = '{db_name}' 
            AND TABLE_NAME = 'detect_log' 
            AND COLUMN_NAME = 'question';
            """
            cursor.execute(check_column_sql)
            column_exists = cursor.fetchone()
            
            if not column_exists:
                add_column_sql = """
                ALTER TABLE detect_log 
                ADD COLUMN question TEXT COMMENT '用户提问文本' 
                AFTER ai_analysis;
                """
                cursor.execute(add_column_sql)
                print("✅ 自动补全缺失的question字段")
            else:
                print("✅ question字段已存在，无需补全")
        
        # 3.3 修复2：自动去掉filename的非空约束（解决1048错误）
        with mysql_conn.cursor() as cursor:
            # 查询filename字段的是否为NOT NULL
            check_null_sql = f"""
            SELECT IS_NULLABLE 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = '{db_name}' 
            AND TABLE_NAME = 'detect_log' 
            AND COLUMN_NAME = 'filename';
            """
            cursor.execute(check_null_sql)
            is_nullable = cursor.fetchone()[0]
            
            # 如果是NO（非空），修改为YES（允许为空）
            if is_nullable == 'NO':
                alter_filename_sql = """
                ALTER TABLE detect_log 
                MODIFY COLUMN filename VARCHAR(255) COMMENT '上传文件名';
                """
                cursor.execute(alter_filename_sql)
                print("✅ 自动修复filename字段：去掉非空约束，允许为空")
            else:
                print("✅ filename字段已允许为空，无需修复")
        
        # 3.4 修复3：detections字段允许为空（纯文字提问时无检测结果）
        with mysql_conn.cursor() as cursor:
            check_detections_null = f"""
            SELECT IS_NULLABLE 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = '{db_name}' 
            AND TABLE_NAME = 'detect_log' 
            AND COLUMN_NAME = 'detections';
            """
            cursor.execute(check_detections_null)
            detections_nullable = cursor.fetchone()[0]
            
            if detections_nullable == 'NO':
                alter_detections_sql = """
                ALTER TABLE detect_log 
                MODIFY COLUMN detections TEXT COMMENT '检测结果JSON字符串';
                """
                cursor.execute(alter_detections_sql)
                print("✅ 自动修复detections字段：去掉非空约束，允许为空")
            else:
                print("✅ detections字段已允许为空，无需修复")
        
        mysql_conn.commit()
        print("✅ MySQL检测日志表 'detect_log' 初始化完成（兼容纯文字/图片交互）")
        return True
    except pymysql.err.OperationalError as e:
        print(f"❌ MySQL连接失败：{str(e)}")
        mysql_conn = None
        return False
    except Exception as e:
        print(f"⚠️ MySQL初始化失败（不影响核心功能）：{str(e)}")
        mysql_conn = None
        return False

def save_to_mysql(filename, question, detections, ai_analysis, file_path):
    """保存交互结果到MySQL，失败仅打印日志（兼容纯文字提问，空值处理）"""
    if not mysql_conn:
        return False
    try:
        insert_sql = """
        INSERT INTO detect_log (filename, question, detections, ai_analysis, create_time, file_path)
        VALUES (%s, %s, %s, %s, %s, %s);
        """
        # 空值处理：None替换为空字符串，避免MySQL null报错
        filename_str = filename if filename else ""
        detections_str = str(detections) if detections else ""
        question_str = question if question else ""
        ai_analysis_str = ai_analysis if ai_analysis else ""
        file_path_str = file_path if file_path else ""
        
        with mysql_conn.cursor() as cursor:
            cursor.execute(insert_sql, (
                filename_str, question_str, detections_str, ai_analysis_str,
                datetime.now(), file_path_str
            ))
        mysql_conn.commit()
        print(f"✅ 交互记录已保存到MySQL：{'文件='+filename if filename else '纯文字提问'}")
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

def save_to_redis(filename, question, detections, ai_analysis, expire=3600):
    """缓存交互结果到Redis（1小时过期），失败仅打印日志"""
    if not redis_client:
        return False
    try:
        # 构造唯一缓存Key（时间戳+文件名/提问摘要）
        cache_key = f"yolo:interact:{int(time.time())}:{filename if filename else 'text'}"
        # 构造缓存值（哈希类型，便于查询）
        cache_value = {
            "question": question or "",
            "detections": str(detections) if detections else "",
            "ai_analysis": ai_analysis,
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "filename": filename or ""
        }
        # 修复Redis hmset弃用警告：替换为hset + mapping参数
        redis_client.hset(cache_key, mapping=cache_value)
        redis_client.expire(cache_key, expire)
        print(f"✅ 交互记录已缓存到Redis：{cache_key}（过期时间{expire}秒）")
        return True
    except Exception as e:
        print(f"⚠️ 保存Redis失败（不影响核心功能）：{str(e)}")
        return False

# ===================== 豆包AI模块（增强：精准回答人数+自由问答） =====================
def call_doubao_ai(question, detections=None):
    """
    增强版AI调用：
    1. 预处理检测结果：自动统计各类目标数量（比如人数），让AI精准回答；
    2. 精准回应：有检测结果时优先回答数量/目标问题，无检测结果时自由回答所有问题；
    3. 容错更强：提示词更清晰，参数更合理，回答更符合自然语言习惯。
    """
    # 兜底提示（AI调用失败时返回）
    fallback_msg = "我是YOLO11智能检测助手，支持图片目标检测和任意问题咨询～你可以上传图片检测目标（人、车、动物等），也可以问任何想知道的问题（比如“今天天气怎么样？”“检测到多少人？”）。"
    
    # 校验豆包API Key是否配置
    if not config.DOUBAO_CONFIG["api_key"] or config.DOUBAO_CONFIG["api_key"] == "你的豆包API Key":
        print("❌ 未配置有效豆包API Key，使用兜底回复")
        return fallback_msg

    # ========== 关键优化1：预处理检测结果，自动统计各类目标数量 ==========
    detect_summary = ""
    if detections and len(detections) > 0:
        # 统计各类目标的数量（比如“人：2个，汽车：1个”）
        target_count = {}
        for item in detections:
            target_type = item["类别"]
            target_count[target_type] = target_count.get(target_type, 0) + 1
        
        # 生成检测结果摘要（让AI直接用，避免解析出错）
        detect_summary = "检测结果统计："
        for target, count in target_count.items():
            detect_summary += f"{target}={count}个；"
        detect_summary = detect_summary.rstrip("；")  # 去掉最后一个分号

    # ========== 关键优化2：分场景设计精准的提示词 ==========
    if detections and len(detections) > 0:
        # 场景1：有检测结果（上传了图片）
        prompt = f"""
        你是一个友好的YOLO11智能助手，需要结合检测结果精准回答用户问题：
        【检测结果统计】：{detect_summary}
        【原始检测结果】：{detections}
        【用户提问】：{question or '请分析检测结果'}
        
        回答要求：
        1. 优先直接回应用户的核心问题（比如问“多少人”就先答人数，再补充其他信息）；
        2. 语言口语化、自然，像聊天一样，不要用技术术语；
        3. 只说关键信息，控制在100字以内；
        4. 如果用户没提问，就主动说明检测到的目标类型和数量。
        """
    else:
        # 场景2：无检测结果（纯文字提问）
        prompt = f"""
        你是一个友好的YOLO11智能助手，能回答用户的任意问题：
        【用户提问】：{question or '打个招呼吧'}
        
        回答要求：
        1. 精准、友好地回答用户的问题，不局限于检测功能（比如天气、闲聊、知识问答都可以）；
        2. 语言口语化、自然，像聊天一样；
        3. 控制在100字以内，简洁易懂。
        """

    try:
        # ========== 关键优化3：调整API参数，让回答更稳定 ==========
        response = requests.post(
            config.DOUBAO_CONFIG["api_url"],
            headers={
                "Authorization": f"Bearer {config.DOUBAO_CONFIG['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": config.DOUBAO_CONFIG["model"],  # 建议用“ernie-4.0-turbo”或“doubao-pro”
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,  # 降低随机性，回答更精准（0-1，越小越稳定）
                "max_tokens": 300     # 调大最大返回字数，避免回答被截断
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
    """主页：渲染大模型风格的对话式检测界面"""
    return render_template('index.html')

@app.route('/detect', methods=['POST'])
def detect():
    """核心交互接口：支持纯文字提问、纯图片检测、文字+图片混合交互"""
    try:
        # 1. 获取请求参数
        user_question = request.form.get('question', '').strip()  # 用户文字提问
        image_file = request.files.get('image')  # 上传的图片
        detections = None  # 检测结果（无图片时为None）
        filename = None
        img_path = None

        # 2. 处理图片检测（如有图片）
        if image_file and image_file.filename != '':
            # 校验文件格式
            if not allowed_file(image_file.filename):
                return jsonify({
                    "code": 400,
                    "msg": f"不支持的文件格式，仅允许：{','.join(config.ALLOWED_EXTENSIONS)}"
                }), 400

            # 保存图片
            filename = os.path.basename(image_file.filename)
            img_path = os.path.join(config.UPLOAD_FOLDER, filename)
            image_file.save(img_path)
            print(f"✅ 上传图片已保存：{img_path}")

            # 执行YOLO检测（模型未加载时返回错误）
            if not model:
                return jsonify({"code": 500, "msg": "YOLO11模型未加载，无法检测图片"}), 500
            
            results = model(img_path)
            # 解析检测结果
            detections = []
            for r in results:
                for box in r.boxes:
                    detections.append({
                        "类别": model.names[int(box.cls)],
                        "置信度": round(float(box.conf), 2),
                        "坐标": [round(x, 2) for x in box.xyxy.tolist()[0]]  # [x1,y1,x2,y2]
                    })

        # 3. 调用豆包AI生成回复（结合提问和检测结果）
        ai_analysis = call_doubao_ai(user_question, detections)

        # 4. 保存结果到MySQL和Redis（失败不影响返回）
        save_to_mysql(filename, user_question, detections, ai_analysis, img_path)
        save_to_redis(filename, user_question, detections, ai_analysis)

        # 5. 返回最终结果
        return jsonify({
            "code": 200,
            "msg": "交互成功（已尝试保存到MySQL/Redis）" if (user_question or filename) else "请输入提问或上传图片",
            "检测结果": detections,  # 无图片时为None
            "豆包AI分析": ai_analysis,
            "用户提问": user_question,
            "文件名称": filename,  # 无图片时为None
            "文件路径": img_path    # 无图片时为None
        }), 200

    except Exception as e:
        # 捕获所有异常，返回友好提示
        print(f"❌ 交互接口异常：{str(e)}")
        return jsonify({"code": 500, "msg": f"处理失败：{str(e)}"}), 500

@app.route('/history', methods=['GET'])
def get_history():
    """查询MySQL中的交互历史记录（最近100条）"""
    # MySQL未初始化时返回错误
    if not mysql_conn:
        return jsonify({"code": 500, "msg": "MySQL未初始化/连接失败，无法查询历史记录"}), 500
    
    try:
        # 查询最近100条记录
        query_sql = """
        SELECT filename, question, detections, ai_analysis, create_time, file_path
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
            # 处理detections空值，避免eval报错
            detections_data = eval(row[2]) if row[2] and row[2] != "" else None
            history_list.append({
                "文件名": row[0] if row[0] else "纯文字提问",
                "用户提问": row[1] if row[1] else "",
                "检测结果": detections_data,
                "豆包AI分析": row[3] if row[3] else "",
                "交互时间": row[4].strftime("%Y-%m-%d %H:%M:%S"),
                "文件路径": row[5] if row[5] else ""
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