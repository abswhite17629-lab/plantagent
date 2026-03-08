# -*- coding: utf-8 -*-
"""
智能体服务
整合检测、RAG、数据库等服务的核心智能体
"""

import torch
from typing import List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_community.llms import HuggingFacePipeline

import config
from services.detection_service import DetectionService
from services.rag_service import RAGService
from services.database_service import DatabaseService


class AgentService:
    """智能体服务类"""

    def __init__(self):
        # 强制禁用GPU
        torch.cuda.is_available = lambda: False

        # 核心组件
        self.llm = None
        self.detection_service = None
        self.rag_service = None
        self.database_service = None

        # 初始化各组件
        self._init_components()

    def _init_components(self):
        """初始化所有组件"""
        print("初始化智能体系统...")

        # 1. 初始化语言模型
        self._init_llm()

        # 2. 初始化检测服务
        self.detection_service = DetectionService()

        # 3. 初始化RAG服务
        self.rag_service = RAGService()

        # 4. 初始化数据库服务
        self.database_service = DatabaseService()

        print("智能体初始化完成！")

    def _init_llm(self):
        """初始化大语言模型"""
        try:
            print("初始化大语言模型...")

            # 根据配置选择不同的模型提供商
            provider = config.LLM_CONFIG["provider"]

            if provider == "openai":
                print("使用OpenAI大模型...")
                self.llm = ChatOpenAI(
                    model=config.LLM_CONFIG["model"],
                    api_key=config.LLM_CONFIG["api_key"],
                    base_url=config.LLM_CONFIG.get("base_url"),
                    temperature=config.LLM_CONFIG.get("temperature", 0.3),
                    max_tokens=config.LLM_CONFIG.get("max_tokens", 1000)
                )

            elif provider == "doubao":
                print("使用豆包大模型...")
                self.llm = ChatOpenAI(
                    model=config.LLM_CONFIG["model"],
                    api_key=config.LLM_CONFIG["api_key"],
                    base_url=config.LLM_CONFIG["base_url"],
                    temperature=config.LLM_CONFIG.get("temperature", 0.3),
                    max_tokens=config.LLM_CONFIG.get("max_tokens", 1000)
                )

            else:
                print("使用本地HuggingFace模型...")
                from transformers import pipeline

                pipe = pipeline(
                    "text-generation",
                    model=config.LLM_CONFIG.get("model", "microsoft/DialoGPT-medium"),
                    max_length=config.LLM_CONFIG.get("max_tokens", 512),
                    temperature=config.LLM_CONFIG.get("temperature", 0.7)
                )

                self.llm = HuggingFacePipeline(pipeline=pipe)

            print(f"大模型初始化成功：{provider}")

        except Exception as e:
            print(f"大模型初始化失败：{str(e)}")
            self.llm = None

    def detect_objects(self, image_path: str) -> List[Dict]:
        """
        执行目标检测

        Args:
            image_path: 图片路径

        Returns:
            检测结果列表
        """
        if not self.detection_service:
            return []
        return self.detection_service.detect_objects(image_path)

    def query_knowledge_base(self, question: str) -> str:
        """
        查询知识库

        Args:
            question: 问题内容

        Returns:
            回答内容
        """
        if not self.rag_service:
            return "知识库系统暂未初始化"
        return self.rag_service.query_knowledge_base(question, self.llm)

    def analyze_detection_results(self, question: str, detections: List[Dict]) -> str:
        """
        分析检测结果

        Args:
            question: 用户问题
            detections: 检测结果

        Returns:
            分析结果
        """
        if not self.rag_service:
            return "AI分析功能暂不可用"
        return self.rag_service.analyze_detection_results(question, detections, self.llm)

    def save_interaction(self, filename: str, question: str, detections: List[Dict],
                        ai_analysis: str, file_path: str = None):
        """
        保存交互记录

        Args:
            filename: 文件名
            question: 问题
            detections: 检测结果
            ai_analysis: AI分析结果
            file_path: 文件路径
        """
        if self.database_service:
            self.database_service.save_interaction(
                filename, question, detections, ai_analysis, file_path
            )

    def add_knowledge_document(self, content: str, metadata: Dict = None) -> bool:
        """
        添加知识文档

        Args:
            content: 文档内容
            metadata: 元数据

        Returns:
            是否成功
        """
        if not self.rag_service:
            return False
        return self.rag_service.add_knowledge_document(content, metadata)

    def get_interaction_history(self, limit: int = 100) -> List[Dict]:
        """
        获取交互历史

        Args:
            limit: 记录数量限制

        Returns:
            历史记录列表
        """
        if not self.database_service:
            return []
        return self.database_service.get_interaction_history(limit)