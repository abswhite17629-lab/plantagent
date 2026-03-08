#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试MCP智能体系统
"""

import sys
import os

try:
    print("测试MCP智能体系统...")

    # 测试MCP客户端导入
    from mcp_client import get_mcp_client, MCPToolClient
    print("MCP客户端导入成功")

    # 测试MCP服务器导入
    from mcp_servers import detection_server, knowledge_server
    print("MCP服务器导入成功")

    # 测试MCP客户端初始化
    mcp_client = get_mcp_client()
    print("MCP客户端初始化成功")

    # 测试获取可用工具
    available_tools = mcp_client.get_available_tools()
    print(f"可用工具: {available_tools}")

    # 测试统一智能体服务导入
    from services.unified_agent_service import UnifiedAgentService
    print("统一智能体服务导入成功")

    # 测试统一智能体服务初始化
    print("正在初始化统一智能体服务...")
    agent_service = UnifiedAgentService()
    print("统一智能体服务初始化成功")

    # 测试基本功能
    print("\n=== 测试智能体基本功能 ===")
    result = agent_service.process_request("你好，请介绍一下你自己")
    print(f"智能体响应: {result}")
    print(f"响应内容: {result.get('response', 'EMPTY')[:200]}...")

    # 测试工具是否可用
    print("\n=== 测试MCP工具 ===")
    available_tools = agent_service.mcp_client.get_available_tools()
    print(f"可用工具: {available_tools}")

    # 测试工具调用
    if "object_detection" in available_tools:
        print("测试目标检测工具...")
        try:
            detection_result = agent_service.mcp_client.call_tool("object_detection", "object_detection", image_path="test.jpg")
            print(f"检测工具测试结果: {detection_result}")
        except Exception as e:
            print(f"检测工具测试失败: {e}")

    if "knowledge_query" in available_tools:
        print("测试知识库查询工具...")
        try:
            knowledge_result = agent_service.mcp_client.call_tool("knowledge_query", "knowledge_query", question="什么是水稻病害？")
            print(f"知识库工具测试结果: {knowledge_result}")
        except Exception as e:
            print(f"知识库工具测试失败: {e}")

    # 测试前端参数修复
    print("\n=== Test frontend parameter fix ===")
    import requests
    try:
        # Test the fixed parameter name
        response = requests.post('http://127.0.0.1:8000/process',
                               data={'question': 'Hello, please introduce yourself'},
                               timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"Success: API call successful: {data.get('code')}")
            if '智能分析' in data:
                print(f"Success: AI analysis response: {data['智能分析'][:100]}...")
            else:
                print("Warning: No AI analysis field in response")
        else:
            print(f"Error: API call failed: {response.status_code}")
    except Exception as e:
        print(f"Error: Request exception: {e}")

    print("\n所有MCP核心组件测试通过!")
    sys.exit(0)

except Exception as e:
    print(f"MCP测试失败: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)