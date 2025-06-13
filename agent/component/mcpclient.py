import asyncio
import os
import json
from typing import Optional, Union, Dict, List, Any, Tuple
from contextlib import AsyncExitStack
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import  sse_client
from mcp.client.stdio import stdio_client
from agent.component.base import ComponentBase, ComponentParamBase
import pandas as pd
from functools import partial
import re
from api.db.services.conversation_service import structure_answer
from api.db.services.llm_service import LLMBundle
from api import settings
from api.db import LLMType
import types
import functools
import time
from rag.utils.redis_conn import REDIS_CONN
import requests

class MCPServerConfig:
    """MCP服务器配置"""
    def __init__(
        self, 
        url: Optional[str] = None,
        command: Optional[str] = None,
        args: List[str] = None,
        env: Dict[str, str] = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: int = 5,
        sse_read_timeout: int = 60 * 5
    ):
        self.url = url
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.headers = headers or {}
        self.timeout = timeout
        self.sse_read_timeout = sse_read_timeout
        
    def validate(self):
        # 互斥校验
        if not (self.url or self.command):
            raise ValueError("必须提供 url 或 command")
        if self.url and self.command:
            raise ValueError("url 和 command 不能同时存在")
        
        # SSE模式校验
        if self.url:
            if not (self.url.startswith('http://') or self.url.startswith('https://')):
                raise ValueError("URL 必须是 http:// 或 https:// 开头")
            if self.headers and not isinstance(self.headers, dict):
                raise TypeError("headers 必须是字典类型")
            if not isinstance(self.timeout, int):
                raise TypeError("timeout 必须是整数")
            if not isinstance(self.sse_read_timeout, int):
                raise TypeError("sse_read_timeout 必须是整数")
        
        # 标准输入输出模式校验
        if self.command:
            if not isinstance(self.command, str):
                raise TypeError("command 必须是字符串")
            if self.args and not isinstance(self.args, list):
                raise TypeError("args 必须是列表类型")
            if self.env and not isinstance(self.env, dict):
                raise TypeError("env 必须是字典类型")

class MCPParam(ComponentParamBase):
    """
    定义MCP组件的参数
    """
    def __init__(self, name: str = None):
        super().__init__()
        self.prompt = ""
        self.debug_inputs = []
        self.server_config: Optional[Union[MCPServerConfig, dict]] = None  # 允许字典类型
        self.cite = True  # 新增引用开关
        self.history_window = 5  # 新增历史截断长度
        if name:
            self.set_name(name)

    def set_server(self, server_config: Union[MCPServerConfig, dict]):
        """处理字典类型的配置"""
        if isinstance(server_config, dict):
            # 移除前端UI专用的type字段
            if 'type' in server_config:
                server_config = server_config.copy()  # 创建副本以避免修改原始对象
                del server_config['type']
            
            # 处理headers字段，如果是字符串则转换为字典
            if 'headers' in server_config and isinstance(server_config['headers'], str):
                try:
                    server_config['headers'] = json.loads(server_config['headers'])
                except json.JSONDecodeError:
                    raise ValueError("[MCP] headers 必须是有效的 JSON 格式")
            
            self.server_config = MCPServerConfig(**server_config)
        else:
            self.server_config = server_config

    def check(self):
        self.check_empty(self.prompt, "[MCP] Prompt")
        if not self.server_config:
            raise ValueError("[MCP] 需要设置服务器配置")
        # 添加类型判断和转换
        if isinstance(self.server_config, dict):
            # 移除前端UI专用的type字段
            if 'type' in self.server_config:
                self.server_config = self.server_config.copy()  # 创建副本以避免修改原始对象
                del self.server_config['type']
            
            # 处理headers字段，如果是字符串则转换为字典
            if 'headers' in self.server_config and isinstance(self.server_config['headers'], str):
                try:
                    self.server_config['headers'] = json.loads(self.server_config['headers'])
                except json.JSONDecodeError:
                    raise ValueError("[MCP] headers 必须是有效的 JSON 格式")
            
            self.server_config = MCPServerConfig(**self.server_config)
        self.server_config.validate()

    def gen_conf(self):
        return {
            "server": {
                "url": self.server_config.url,
                "command": self.server_config.command,
                "args": self.server_config.args,
                "env": self.server_config.env
            }
        }

class MCP(ComponentBase):
    component_name = "MCP"
    
    # 用于缓存工具的Redis键
    REDIS_CACHED_TOOLS_KEY = "mcp:cached_tools"
    
    @classmethod
    def clear_all_redis_tools(cls):
        """
        清空Redis中所有缓存的工具列表
        
        该方法会：
        1. 删除Redis中存储的工具缓存
        2. 记录清理操作的日志
        
        使用场景：
        - 服务关闭时
        - 需要强制刷新工具列表时
        - 缓存出现异常时
        """
        try:
            # 删除Redis中的工具缓存
            REDIS_CONN.REDIS.delete(cls.REDIS_CACHED_TOOLS_KEY)
            print("[MCP Debug] Redis工具缓存已清空")
                    
        except Exception as e:
            print(f"[MCP Debug] 清空Redis工具缓存失败: {str(e)}")
            raise

    def __init__(self, canvas, id, param: Union[str, MCPParam], api_key: str, model_name: str, base_url: str = None):
        if isinstance(param, str):
            param = MCPParam(param)
        super().__init__(canvas, id, param)
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.exit_stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None
        self.stdio = None
        self.write = None
        # 添加工具缓存
        self._cached_tools = None
        self._connection_initialized = False

    def get_cached_tools(self):
        """从Redis获取缓存的工具"""
        if self._cached_tools is None:
            # 尝试从Redis获取
            cached_data = REDIS_CONN.get(self.REDIS_CACHED_TOOLS_KEY)
            if cached_data:
                try:
                    self._cached_tools = json.loads(cached_data)
                    print(f"[MCP Debug] 从redis获取到{len(self._cached_tools)}个工具")
                except json.JSONDecodeError:
                    self._cached_tools = None
        return self._cached_tools

    def set_cached_tools(self, tools):
        """将工具缓存到Redis"""
        self._cached_tools = tools
        try:
            # 将工具数据序列化并存储到Redis，设置24小时过期
            REDIS_CONN.set_obj(self.REDIS_CACHED_TOOLS_KEY, tools, exp=24*3600)
            print(f"[MCP Debug] 缓存工具到Redis成功,24小时后过期")
        except Exception as e:
            print(f"[MCP Debug] 缓存工具到Redis失败: {str(e)}")   

    async def connect_to_server(self) -> ClientSession:
        """连接到服务器"""
        # 如果已经有活跃连接，则直接返回
        if self._connection_initialized and self.session is not None:
            try:
                # 简单测试连接是否有效
                await self.session.ping()
                print("[MCP Debug] 使用现有连接")
                return self.session
            except Exception as e:
                print(f"[MCP Debug] 现有连接已失效，重新连接: {str(e)}")
                # 连接已失效，重新连接
                self._connection_initialized = False
                self._cached_tools = None
                await self.disconnect_from_server()
        
        # 在连接前确保清理旧资源
        await self.disconnect_from_server()
        
        server_config = self._param.server_config
        print("正在连接到服务器...")

        try:
            async def _connect():
                # 使用新的exit_stack管理连接
                if server_config.url:
                    stdio_transport = await self.exit_stack.enter_async_context(
                        sse_client(
                            server_config.url,
                            headers=server_config.headers,
                            timeout=server_config.timeout,
                            sse_read_timeout=server_config.sse_read_timeout
                        )
                    )
                else:
                    server_params = StdioServerParameters(
                        command=server_config.command,
                        args=server_config.args,
                        env=server_config.env
                    )
                    stdio_transport = await self.exit_stack.enter_async_context(
                        stdio_client(server_params)
                    )

                self.stdio, self.write = stdio_transport
                self.session = await self.exit_stack.enter_async_context(
                    ClientSession(self.stdio, self.write)
                )
                await self.session.initialize()
                self._connection_initialized = True
                return self.session

            return await asyncio.wait_for(_connect(), timeout=30)

        except asyncio.TimeoutError:
            print("连接服务器超时")
            self._connection_initialized = False
            raise
        except Exception as e:
            print(f"连接服务器时发生错误: {str(e)}")
            self._connection_initialized = False
            raise

    async def disconnect_from_server(self):
        """断开与服务器的连接"""
        try:
            # 先关闭底层传输
            if self.stdio:
                await self.stdio.aclose()
            if self.write:
                await self.write.aclose()
        except Exception as e:
            print(f"关闭传输时发生错误: {str(e)}")
        finally:
            try:
                # 最后关闭 exit_stack
                if self.exit_stack:
                    await self.exit_stack.aclose()
            except RuntimeError as e:
                if "different task" not in str(e):
                    print(f"断开连接时发生错误: {str(e)}")
            finally:
                # 创建新的 AsyncExitStack 实例
                self.exit_stack = AsyncExitStack()
                # 重置其他连接相关属性
                self.session = None
                self.stdio = None
                self.write = None
                self._connection_initialized = False

    async def cleanup(self):
        """清理服务器连接"""
        try:
            # 实际不再每次聊天后清理连接，仅在实例销毁时做最终清理
            # await self.disconnect_from_server() 
            pass
        except Exception as e:
            print(f"清理资源时发生错误: {str(e)}")
            # 不抛出异常，确保清理过程不会中断主流程

    # 新增获取工具列表的方法，支持缓存
    async def get_tool_list(self):
        """获取工具列表，优先使用Redis缓存"""
        # 尝试从Redis缓存获取工具列表
        cached_tools = self.get_cached_tools()
        if cached_tools is not None:
            session = await self.connect_to_server()
            print(f"[MCP Debug] 使用Redis缓存的工具列表，共{len(cached_tools)}个工具")
            return cached_tools
            
        print("[MCP Debug] Redis缓存未命中，正在获取工具列表...")
        session = await self.connect_to_server()
        response = await session.list_tools()
        tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
        } for tool in response.tools]
        
        # 将工具列表缓存到Redis
        print(f"[MCP Debug] 获取到{len(tools)}个工具，正在缓存到Redis")
        self.set_cached_tools(tools)
        return tools

    def get_input_elements(self):
        """获取输入元素，处理prompt中的引用"""
        key_set = set([])
        res = [{"key": "user", "name": "Input your question here:"}]
        
        print(f"\n[Input Elements Debug] 开始处理prompt中的引用")
        print(f"[Input Elements Debug] 原始prompt: {self._param.prompt}")
        
        # 修改正则表达式匹配模式
        pattern = r"\{([a-z]+@[a-z0-9_-]+)\}"  # 更精确匹配begin@格式
        for r in re.finditer(pattern, self._param.prompt, flags=re.IGNORECASE):
            cpn_id = r.group(1)
            print(f"\n[Input Elements Debug] 发现引用: {cpn_id}")
            
            if cpn_id in key_set:
                print(f"[Input Elements Debug] 跳过重复引用: {cpn_id}")
                continue
                
            # 添加格式校验
            if '@' not in cpn_id:
                continue
                
            # 处理特殊的begin@引用
            if cpn_id.lower().find("begin@") == 0:
                print(f"[Input Elements Debug] 处理begin@引用: {cpn_id}")
                cpn_id, key = cpn_id.split("@")
                component = self._canvas.get_component(cpn_id)
                if not component:
                    print(f"[Input Elements Debug] 未找到组件: {cpn_id}")
                    continue
                    
                print(f"[Input Elements Debug] 查找参数: {key} in {cpn_id}")
                for p in component["obj"]._param.query:
                    if p["key"] != key:
                        continue
                    print(f"[Input Elements Debug] 找到参数: {p['name']} = {p.get('value', '')}")
                    res.append({"key": r.group(1), "name": p["name"]})
                    key_set.add(r.group(1))
                continue
                
            # 处理普通组件引用
            print(f"[Input Elements Debug] 处理普通组件引用: {cpn_id}")
            cpn_nm = self._canvas.get_component_name(cpn_id)
            if not cpn_nm:
                print(f"[Input Elements Debug] 未找到组件名称: {cpn_id}")
                continue
            print(f"[Input Elements Debug] 找到组件: {cpn_id} -> {cpn_nm}")
            res.append({"key": cpn_id, "name": cpn_nm})
            key_set.add(cpn_id)
            
        print(f"\n[Input Elements Debug] 处理完成")
        print(f"[Input Elements Debug] 找到的引用: {[r['key'] for r in res]}")
        return res

    async def process_query(self, system_prompt: str = None, history: list = None) -> str:
        """处理查询并调用工具，增加系统提示和历史支持"""
        print("开始处理查询...")
        # 初始化OpenAI客户端
        if not self.client:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

        # 确保第一条消息是user消息
        if not history:
            history = [{"role": "user", "content": "请开始分析"}]
        elif history[0].get("role") == "assistant":
            history = history[1:]  # 跳过第一条assistant消息
            if not history:  # 如果跳过之后为空，添加默认user消息
                history = [{"role": "user", "content": "请开始分析"}]
        
        # 构建消息历史
        messages = []
        if history:
            # 检查消息格式并进行适当处理
            if history and isinstance(history[0], dict) and "role" in history[0]:
                # 消息已经是字典格式，确保没有空的tool_calls数组
                print(f"[Process Query] 使用预格式化的消息历史，长度: {len(history)}")
                for msg in history:  # 不再跳过第一条消息
                    # 创建新的消息对象，避免修改原始对象
                    message_dict = {
                        "role": msg["role"],
                        "content": msg["content"]
                    }
                    # 只有在确实有工具调用时才添加tool_calls字段
                    if "tool_calls" in msg and msg["tool_calls"] and len(msg["tool_calls"]) > 0:
                        message_dict["tool_calls"] = msg["tool_calls"]
                    messages.append(message_dict)
            else:
                # 消息是元组或列表格式，需要转换
                print(f"[Process Query] 转换消息历史格式，长度: {len(history)}")
                for msg in history:
                    if isinstance(msg, (list, tuple)) and len(msg) >= 2:
                        messages.append({
                            "role": msg[0],
                            "content": msg[1]
                        })
                    else:
                        print(f"[Process Query] 警告: 跳过无效消息格式: {msg}")

        try:
            # 获取工具列表（使用缓存机制）
            tools = await self.get_tool_list()

            # 添加循环处理工具调用
            max_iterations = 10  # 安全阀防止无限循环
            while max_iterations > 0:
                max_iterations -= 1
                
                # 构建完整消息，包含系统提示
                full_messages = []
                if system_prompt:
                    full_messages.append({"role": "system", "content": system_prompt})
                
                # 添加历史记录截断逻辑
                NUM_RECENT_MESSAGES_TO_KEEP = 15  # 定义要保留的最近用户/助手消息数量
                
                if len(messages) > NUM_RECENT_MESSAGES_TO_KEEP:
                    print(f"[Process Query] 原始消息数: {len(messages)}")
                    # 保留最后 N 条消息
                    truncated_messages = messages[-NUM_RECENT_MESSAGES_TO_KEEP:]
                    print(f"[Process Query] 截断：保留最后 {NUM_RECENT_MESSAGES_TO_KEEP} 条消息。截断后消息数: {len(truncated_messages)}")
                else:
                    # 历史记录足够短，使用所有消息
                    truncated_messages = messages
                    print(f"[Process Query] 历史记录较短，使用所有消息。数量: {len(truncated_messages)}")
                
                full_messages.extend(truncated_messages)
                
                print(f"[Process Query] 发送消息到API，消息数: {len(full_messages)}")
                for i, msg in enumerate(full_messages):
                    print(f"[Process Query] 消息 {i}: 角色={msg.get('role')}, 内容长度={len(str(msg.get('content', '')))}")
                    if "tool_calls" in msg:
                        print(f"[Process Query] 消息 {i} 包含 {len(msg['tool_calls'])} 个工具调用")
                
                # 调用OpenAI API
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=full_messages,
                    tools=tools,
                    temperature=0.3
                )

                content = response.choices[0]
                print(f"API 返回的 finish_reason: {content.finish_reason}")
                
                if content.finish_reason != "tool_calls":
                    return content.message.content

                # 处理所有工具调用
                tool_messages = []
                for tool_call in content.message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    print(f"[Process Query] 准备调用工具: {tool_name}")
                    result = await self.session.call_tool(tool_name, tool_args)
                    
                    # 为每个工具调用添加响应
                    tool_messages.append({
                        "role": "tool",
                        "content": result.content[0].text if result.content else "",
                        "tool_call_id": tool_call.id,
                    })

                # 更新消息历史
                # 确保有tool_calls时才添加
                assistant_message = content.message.model_dump()
                messages.append(assistant_message)
                messages.extend(tool_messages)

            return "达到最大迭代次数，终止处理"

        except Exception as e:
            print(f"处理查询时发生错误: {str(e)}")
            import traceback
            print("错误堆栈:")
            print(traceback.format_exc())
            # 连接错误时清除缓存
            self._cached_tools = None
            self._connection_initialized = False
            raise
        finally:
            # 不再在每次查询后断开连接
            pass

    async def process_query_streamly(self, system_prompt: str, history: list,):
        """修改为真正的异步生成器"""
        print(f"[MCP Debug] 进入流式处理流程 | 初始消息长度: {len(history)}")
        messages = []
        full_content = ""  # 新增全量内容累加器
        tool_citations = []  # 新增工具调用引用收集
        assistant_content = ""  # 新增：记录大模型的输出内容
        
        # 确保第一条消息是user消息
        if not history:
            history = [{"role": "user", "content": "请开始分析"}]
        elif history[0].get("role") == "assistant":
            history = history[1:]  # 跳过第一条assistant消息
            if not history:  # 如果跳过之后为空，添加默认user消息
                history = [{"role": "user", "content": "请开始分析"}]

        # 获取最新的用户消息并处理引用
        query = ""
        if history and len(history) > 0:
            if isinstance(history[-1], dict) and "role" in history[-1]:
                query = history[-1].get("content", "")
            elif isinstance(history[-1], (list, tuple)) and len(history[-1]) >= 2:
                query = history[-1][1]
        
        query, citations = self._preprocess_input(query)
        print(f"[MCP Debug] 流式处理 | 原始查询: {query} | 引用数: {len(citations)}")
        
        # 添加系统消息
        system_message = {"role": "system", "content": system_prompt}
        messages.append(system_message)

        print(f"[MCP Debug] 初始消息: {messages}")
        
        try:
            # 处理历史消息，确保格式一致
            if history:
                print(f"[MCP Debug] 合并历史消息 | 原消息数: {len(messages)} | 新增历史消息数: {len(history)}")
                
                for msg in history:
                    if isinstance(msg, dict) and "role" in msg:
                        # 已经是字典格式，创建新对象避免修改原始对象
                        message_dict = {
                            "role": msg["role"],
                            "content": msg["content"]
                        }
                        # 只有在确实有工具调用时才添加tool_calls字段
                        if "tool_calls" in msg and msg["tool_calls"] and len(msg["tool_calls"]) > 0:
                            message_dict["tool_calls"] = msg["tool_calls"]
                        messages.append(message_dict)
                    elif isinstance(msg, (list, tuple)) and len(msg) >= 2:
                        # 列表或元组格式，转换为字典
                        messages.append({
                            "role": msg[0],
                            "content": msg[1]
                        })
                    else:
                        print(f"[MCP Debug] 警告：跳过无效消息格式: {msg}")
                
                print(f"[MCP Debug] 合并历史消息完成 | 总消息数: {len(messages)}")
                
            # 初始化OpenAI客户端（如果需要）
            if not self.client:
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
            
            # 获取工具列表（使用缓存机制）
            tools = await self.get_tool_list()
            
            max_iterations = 100
            full_content = ""  # 重置全量内容
            assistant_content = ""  # 重置大模型输出内容
            tool_content = ""  # 新增：记录工具调用相关内容
            
            while max_iterations > 0:
                max_iterations -= 1
                
                # 添加历史记录截断逻辑
                NUM_RECENT_MESSAGES_TO_KEEP = 15 # 定义要保留的最近用户/助手消息数量
                
                if len(messages) > NUM_RECENT_MESSAGES_TO_KEEP:
                    print(f"[History Debug] 原始消息数: {len(messages)}")
                    # 检查第一条消息是否为系统提示
                    if messages[0].get('role') == 'system':
                        # 保留系统提示和最后 N 条消息
                        truncated_messages = [messages[0]] + messages[-NUM_RECENT_MESSAGES_TO_KEEP:]
                        print(f"[History Debug] 截断：保留系统提示和最后 {NUM_RECENT_MESSAGES_TO_KEEP} 条消息。截断后消息数: {len(truncated_messages)}")
                    else:
                        # 没有系统提示，仅保留最后 N 条消息
                        truncated_messages = messages[-NUM_RECENT_MESSAGES_TO_KEEP:]
                        print(f"[History Debug] 截断：保留最后 {NUM_RECENT_MESSAGES_TO_KEEP} 条消息。截断后消息数: {len(truncated_messages)}")
                else:
                    # 历史记录足够短，使用所有消息
                    truncated_messages = messages
                    print("[History Debug] 历史记录较短，使用所有消息。")
                
                # 打印发送给API的消息 (可选调试)
                # print(f"[Stream Debug] 发送消息到API，消息数: {len(truncated_messages)}\")\n                # for i, msg in enumerate(truncated_messages):\n                #     print(f\"[Stream Debug] 消息 {i}: 角色={msg.get('role')}, 内容长度={len(str(msg.get('content', '')))}\")\n                #     if \"tool_calls\" in msg:\n                #         print(f\"[Stream Debug] 消息 {i} 包含 {len(msg['tool_calls'])} 个工具调用\")\n                \n                stream = self.client.chat.completions.create(\n                    model=self.MODEL_NAME,\n                    messages=truncated_messages, # <--- 使用截断后的消息列表\n                    tools=tools,\n                    stream=True\n                )\n\n                tool_calls = []\n                # ... rest of the loop ...\
                
                stream = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=truncated_messages,
                    tools=tools,
                    stream=True
                )

                tool_calls = []
                current_tool_call = None
                current_chunk_content = ""  # 用于累积当前chunk的内容
                
                for chunk in stream:
                    content = chunk.choices[0].delta
                    if content.content:
                        current_chunk_content += content.content
                        assistant_content += content.content
                        full_content = assistant_content + tool_content  # 合并内容
                        yield {"content": full_content, "reference": [], "running_status": True}
                    
                    # 收集工具调用信息
                    if content.tool_calls:
                        for tool_call in content.tool_calls:
                            if tool_call.id:
                                current_tool_call = {
                                    "id": tool_call.id,
                                    "function": {
                                        "name": "",
                                        "arguments": ""
                                    }
                                }
                                tool_calls.append(current_tool_call)
                            
                            if current_tool_call:
                                current_tool_call["function"]["name"] += tool_call.function.name or ""
                                current_tool_call["function"]["arguments"] += tool_call.function.arguments or ""
                
                # 处理工具调用
                if tool_calls:
                    # 添加工具调用开始标记
                    tool_content += "\n<think>\n（正在调用工具：\n\n"
                    full_content = assistant_content + tool_content
                    yield {"content": full_content, "reference": [], "running_status": True}
                    
                    # 确保有工具调用时才添加tool_calls字段
                    assistant_msg = {
                        "role": "assistant",
                        "content": current_chunk_content
                    }
                    
                    if tool_calls:
                        assistant_msg["tool_calls"] = [
                            {
                                "id": tc["id"],
                                "function": {
                                    "name": tc["function"]["name"],
                                    "arguments": tc["function"]["arguments"]
                                },
                                "type": "function"
                            } for tc in tool_calls
                        ]
                    
                    messages.append(assistant_msg)
                    
                    tool_messages = []
                    for tool_call in tool_calls:
                        try:
                            # 添加工具调用信息
                            tool_name = tool_call["function"]["name"]
                            args_str = tool_call["function"]["arguments"].strip()
                            tool_content += f"{tool_name}({args_str})...\n"
                            full_content = assistant_content + tool_content
                            yield {"content": full_content, "reference": [], "running_status": True}
                            
                            # 执行工具调用
                            tool_args = json.loads(args_str)
                            result = await self.session.call_tool(tool_name, tool_args)
                            
                            # 添加工具调用结果到引用
                            tool_citation = {
                                "doc_id": f"tool_{len(tool_citations)}",
                                "docnm_kwd": f"{tool_name}调用结果",
                                "content_ltks": result.content[0].text if result.content else "无返回内容",
                                "vector": None
                            }
                            tool_citations.append(tool_citation)
                            
                            # 添加工具调用结果
                            tool_result = f"工具返回：\n{result.content[0].text if result.content else '无返回内容'}\n"
                            tool_content += tool_result
                            full_content = assistant_content + tool_content
                            yield {"content": full_content, "reference": [], "running_status": True}
                            
                            tool_messages.append({
                                "role": "tool",
                                "content": result.content[0].text if result.content else "无返回内容",
                                "tool_call_id": tool_call["id"],
                            })

                        except json.JSONDecodeError:
                            tool_content += f"（参数解析失败：{args_str}）\n"
                        except Exception as e:
                            tool_content += f"（工具执行失败：{str(e)}）\n"
                        
                        full_content = assistant_content + tool_content
                        yield {"content": full_content, "reference": [], "running_status": True}
                    
                    # 添加工具调用结束标记
                    tool_content += "）</think>\n"
                    full_content = assistant_content + tool_content
                    yield {"content": full_content, "reference": [], "running_status": True}
                    
                    messages.extend(tool_messages)
                else:
                    # 没有工具调用，添加普通的助手消息
                    if current_chunk_content:
                        messages.append({
                            "role": "assistant",
                            "content": current_chunk_content
                        })
                    break

            # 在流式输出结束时，添加完整的引用结构
            if self._param.cite:
                all_citations = citations + tool_citations
                # 对大模型的输出内容添加引用标记
                final_response = self._add_citations_from_tools(assistant_content, all_citations)
                # 将工具调用内容添加到带引用的响应后面
                if tool_content:
                    final_response["content"] = final_response["content"] + tool_content
                print("[Stream Debug] 生成最终带引用的响应")
                yield final_response

        except Exception as e:
            print(f"[MCP Error] 流式处理异常: {str(e)}")
            import traceback
            print(f"异常堆栈:\n{traceback.format_exc()}")
            raise
        finally:
            await self.cleanup()

    def _run(self, history, **kwargs):
        """运行MCP客户端，处理查询并返回结果"""
        # 在开头添加空值保护
        if not hasattr(self, '_param') or not hasattr(self._param, 'prompt'):
            return pd.DataFrame([{"content": "组件配置错误"}])
        
        # 添加prompt预处理
        processed_prompt = re.sub(r"\s+", " ", self._param.prompt).strip()
        self._param.prompt = processed_prompt

        # 从history中提取最新用户消息
        query = ""
        if history and isinstance(history[-1], (list, tuple)) and history[-1][0] == "user":
            query = history[-1][1]
            print(f"[MCP Debug] 从history提取用户问题: {query}")
        else:
            query = kwargs.get("user", "")
            print(f"[MCP Debug] 从kwargs获取用户问题: {query}")

        # 参数替换到prompt
        print("\n[Prompt Debug] 开始处理prompt替换")
        print(f"[Prompt Debug] 原始prompt: {self._param.prompt}")
        print(f"[Prompt Debug] 可用参数: {list(kwargs.keys())}")
        
        # 保存原始prompt用于显示
        original_prompt = self._param.prompt

        # 先处理特殊的{input}引用（重要：先处理input再处理组件引用）
        retrieval_res = []
        if self._param.prompt.find("{input}") >= 0:
            print("\n[Input Debug] 发现{input}引用，开始处理")
            input_res = self.get_input()
            if "content" in input_res.columns:
                input_content = ("  - " + "\n  - ".join(
                    [c for c in input_res["content"] if isinstance(c, str)]))
                print(f"[Input Debug] 获取到输入内容: {input_content[:100]}...")
                self._param.prompt = re.sub(r"\{input\}", input_content, self._param.prompt)
                if "vector" in input_res.columns and "content_ltks" in input_res.columns:
                    retrieval_res.append(input_res)
                    print("[Input Debug] 添加input检索结果到引用列表")
        
        # 处理组件引用
        self._param.inputs = []
        for para in self.get_input_elements()[1:]:
            print(f"\n[Component Debug] 处理组件引用: {para}")
            
            # 排除已处理的input引用
            if para["key"].lower() == "input":
                print(f"[Component Debug] 跳过已处理的input引用")
                continue
                
            # 处理begin@引用
            if para["key"].lower().find("begin@") == 0:
                print(f"[Component Debug] 处理begin@引用: {para['key']}")
                cpn_id, key = para["key"].split("@")
                for p in self._canvas.get_component(cpn_id)["obj"]._param.query:
                    if p["key"] == key:
                        kwargs[para["key"]] = p.get("value", "")
                        self._param.inputs.append(
                            {"component_id": para["key"], "content": kwargs[para["key"]]})
                        print(f"[Component Debug] begin@引用结果: {kwargs[para['key']]}")
                        break
                else:
                    assert False, f"Can't find parameter '{key}' for {cpn_id}"
                continue

            # 处理普通组件引用
            component_id = para["key"]
            print(f"[Component Debug] 处理普通组件引用: {component_id}")
            cpn = self._canvas.get_component(component_id)["obj"]
            
            # 处理Answer组件
            if cpn.component_name.lower() == "answer":
                print("[Component Debug] 处理Answer组件引用")
                hist = self._canvas.get_history(1)
                if hist:
                    hist = hist[0]["content"]
                else:
                    hist = ""
                kwargs[para["key"]] = hist
                print(f"[Component Debug] Answer组件结果: {hist}")
                continue
                
            # 处理其他组件
            _, out = cpn.output(allow_partial=False)
            if "content" not in out.columns:
                print(f"[Component Debug] 组件{component_id}无content输出")
                kwargs[para["key"]] = ""
            else:
                if cpn.component_name.lower() == "retrieval":
                    print(f"[Component Debug] 添加Retrieval组件结果到引用列表")
                    retrieval_res.append(out)
                kwargs[para["key"]] = "  - " + "\n  - ".join([o if isinstance(o, str) else str(o) for o in out["content"]])
                print(f"[Component Debug] 组件{component_id}处理结果: {kwargs[para['key']][:100]}...")
            self._param.inputs.append({"component_id": para["key"], "content": kwargs[para["key"]]})

        # 合并检索结果
        if retrieval_res:
            print("\n[Retrieval Debug] 合并检索结果")
            retrieval_res = pd.concat(retrieval_res, ignore_index=True)
            print(f"[Retrieval Debug] 合并后数量: {len(retrieval_res)}")
        else:
            print("\n[Retrieval Debug] 无检索结果")
            retrieval_res = pd.DataFrame([])

        # 替换所有参数到prompt
        for n, v in kwargs.items():
            old_prompt = self._param.prompt
            self._param.prompt = re.sub(r"\{%s\}" % re.escape(n), str(v).replace("\\", " "), self._param.prompt)
            if old_prompt != self._param.prompt:
                print(f"\n[Prompt Debug] 替换参数 {n}:")
                print(f"  - 替换前: {old_prompt}")
                print(f"  - 替换后: {self._param.prompt}")

        print("\n[Prompt Debug] 最终prompt处理结果:")
        print(f"原始: {original_prompt}")
        print(f"替换后: {self._param.prompt}")

        # 构建系统提示
        system_prompt = self._param.prompt
        print(f"[MCP Debug] 系统提示构建完成: {system_prompt}")

        # 处理历史消息
        messages = []
        if history:
            for msg in history:
                # 不要添加空的tool_calls数组
                message_dict = {
                    "role": msg[0],
                    "content": msg[1]
                }
                # 只有在确实有工具调用时才添加tool_calls字段
                # 这解决了"empty array. Expected an array with minimum length 1"错误
                messages.append(message_dict)

        # 初始化OpenAI客户端（保持原有逻辑）
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        # 流式处理判断（保持原有逻辑）
        downstreams = []
        if self._canvas:
            component_info = self._canvas.get_component(self._id)
            downstreams = component_info.get("downstream", []) if component_info else []
        
        if kwargs.get("stream") and downstreams:
            return functools.partial(self._sync_stream_wrapper, system_prompt, messages)

        # 创建事件循环来调用异步方法
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 调用工具处理查询
            result = loop.run_until_complete(
                self.process_query(system_prompt=system_prompt, history=messages)
                # self.stream_output(system_prompt=system_prompt, history=messages)
            )
            
            # 如果有检索结果，添加引用
            if not retrieval_res.empty and "content_ltks" in retrieval_res.columns and "vector" in retrieval_res.columns:
                print("\n[Citation Debug] 添加引用到结果")
                result = self.set_cite(retrieval_res, result)
                print(f"[Citation Debug] 添加引用后的结果: {result}")
            
            return pd.DataFrame([{"content": result}])
        except Exception as e:
            print(f"[MCP Error] 处理查询时发生错误: {str(e)}")
            import traceback
            print(f"错误堆栈:\n{traceback.format_exc()}")
            raise e
        finally:
            loop.close()
            print("[MCP Debug] 事件循环已关闭")

    # 新增同步包装方法
    def _sync_stream_wrapper(self, system_prompt, history):
        """优化事件循环管理"""
        print(f"[SYNC WRAPPER] 进入同步包装器")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async_gen = self.stream_output(system_prompt, history)
        
        try:
            while True:
                try:
                    chunk = loop.run_until_complete(async_gen.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break
        finally:
            loop.close()
            print("[SYNC WRAPPER] 事件循环已关闭")

    # 新增辅助方法
    def _preprocess_input(self, query: str) -> tuple:
        """增强的预处理方法，支持检索"""
        # 解析显式引用
        citations = []
        pattern = r"@\[([^\]]+)\]\[([^\]]+)\]"
        matches = re.findall(pattern, query)
        
        # 处理显式引用
        for match in matches:
            citations.append({"name": match[0], "id": match[1]})
            query = query.replace(f"@[{match[0]}][{match[1]}]", "")
        
        # 添加隐式检索逻辑（与Generate一致）
        retrieval_res = self.get_input()
        # 增加字段存在性检查（关键修改）
        if not retrieval_res.empty and "doc_id" in retrieval_res.columns:
            citations.extend([{
                "doc_id": row.get("doc_id", ""),
                "docnm_kwd": row.get("docnm_kwd", ""),
                "content_ltks": row.get("content_ltks", ""),
                "vector": row.get("vector", "")
            } for _, row in retrieval_res.iterrows()])
        
        return query.strip(), citations  # 移除pd.DataFrame转换

    def _build_system_prompt(self, citations: list) -> str:  # 参数类型改为list
        """构建带引用的系统提示"""
        base_prompt = self._param.prompt
        if not citations:
            return base_prompt
        
        citation_text = "\n".join([
            f"文档《{cite['name']}》（ID:{cite['id']}）已提供，请优先参考"
            if 'name' in cite else  # 处理不同格式的引用
            f"文档《{cite['docnm_kwd']}》（ID:{cite['doc_id']}）已提供，请优先参考"
            for cite in citations
        ])
        
        return f"{base_prompt}\n\n当前对话可参考以下文档：\n{citation_text}"

    def _truncate_history(self, history: list) -> list:
        """历史对话截断"""
        window_size = max(0, self._param.history_window)
        return history[-window_size:]

    def _add_citations(self, response: str, citations: list) -> dict:
        """统一的结构化输出"""
        if not citations:
            return {"content": response, "reference": {"chunks": [], "doc_aggs": []}}
        
        return self.set_cite(citations, response)

    async def stream_output(self, system_prompt, history):
        """优化后的流式输出方法"""
        try:
            print(f"[STREAM OUTPUT] 开始流式输出处理 | history长度: {len(history)}")
            full_response = ""
            chunk_count = 0
            
            # 获取原始生成器
            raw_generator = self.process_query_streamly(system_prompt, history)
            
            # 异步迭代并解包（关键修改）
            async for raw_chunk in raw_generator:
                # 如果chunk本身是生成器，进行深度解包
                if isinstance(raw_chunk, types.GeneratorType):
                    print(f"[STREAM OUTPUT] 检测到嵌套生成器，开始深度解包")
                    try:
                        while True:
                            sub_chunk = await raw_chunk.__anext__()
                            chunk_count += 1
                            formatted = self._format_chunk(sub_chunk, chunk_count)
                            yield formatted
                    except StopAsyncIteration:
                        continue
                else:
                    chunk_count += 1
                    formatted = self._format_chunk(raw_chunk, chunk_count)
                    yield formatted

            print(f"[STREAM OUTPUT] 流式处理完成 | 总chunk数: {chunk_count} | 总长度: {len(full_response)}")
            
        except Exception as e:
            print(f"[STREAM OUTPUT ERROR] 流式输出异常: {str(e)}")
            import traceback
            print(f"异常堆栈:\n{traceback.format_exc()}")
            # 只有在异常时清除缓存并断开连接
            self._cached_tools = None 
            self._connection_initialized = False
            await self.disconnect_from_server()
            raise
        finally:
            # 不再在每次流式输出后清理资源
            print("[STREAM OUTPUT] 流式输出完成")

    def _format_chunk(self, chunk, count):
        """统一格式化输出块"""
        # 确保输出结构符合Canvas预期
        return {
            "content": chunk.get("content", ""),
            "running_status": count == 1,  # 首个chunk标记为运行状态
            "reference": chunk.get("reference", {})
        }

    @staticmethod
    def be_output(content):
        """格式化输出"""
        return pd.DataFrame([{"content": content}]) 

    def debug(self, **kwargs):
        """调试方法，用于测试组件功能"""
        if self._param.debug_inputs:
            query = self._param.debug_inputs[0].get("value", "")
        else:
            query = kwargs.get("user", "")
            
        if not query:
            return pd.DataFrame([{"content": "请输入您的问题"}])
            
        self._param.check()
            
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 使用新的带有系统提示和历史的处理查询方法
            response = loop.run_until_complete(
                self.process_query(query, self._param.prompt, [])
            )
            return pd.DataFrame([{"content": response}])
        except Exception as e:
            # 在异常情况下清理资源
            loop.run_until_complete(self.final_cleanup())
            raise e
        finally:
            loop.close()

    def set_cite(self, retrieval_res, answer):
        """与Generate组件保持一致的引用处理逻辑"""
        # 确保包含必要字段
        retrieval_res = retrieval_res.dropna(subset=["vector", "content_ltks"]).reset_index(drop=True)
        
        # 插入引用标注
        answer, idx = settings.retrievaler.insert_citations(
            answer,
            [ck["content_ltks"] for _, ck in retrieval_res.iterrows()],
            [ck["vector"] for _, ck in retrieval_res.iterrows()],
            LLMBundle(self._canvas.get_tenant_id(), LLMType.EMBEDDING, 
                     self._canvas.get_embedding_model()),
            tkweight=0.7,
            vtweight=0.3
        )
        
        # 构建参考文献结构
        doc_ids = set()
        recall_docs = []
        for i in idx:
            did = retrieval_res.loc[int(i), "doc_id"]
            if did not in doc_ids:
                doc_ids.add(did)
                recall_docs.append({
                    "doc_id": did,
                    "doc_name": retrieval_res.loc[int(i), "docnm_kwd"]
                })
        
        reference = {
            "chunks": [ck.to_dict() for _, ck in retrieval_res.iterrows()],
            "doc_aggs": recall_docs
        }

        print(f"[MCP Debug] 引用结果: {reference}")
        
        # 结构化输出
        res = {"content": answer, "reference": reference}
        return structure_answer(None, res, "", "") 

    # 新增方法用于最终清理
    async def final_cleanup(self):
        """最终清理，通常在组件实例销毁时调用"""
        try:
            # 确保关闭所有连接
            await self.disconnect_from_server()
            self._cached_tools = None
            self._connection_initialized = False
        except Exception as e:
            print(f"最终清理资源时发生错误: {str(e)}") 

    def __del__(self):
        """析构函数，确保对象被销毁时释放资源"""
        try:
            # 在析构函数中只进行同步清理
            self._cached_tools = None
            self._connection_initialized = False
            # 注意：这里不调用异步的 disconnect_from_server
            # 如果需要清理连接，应该在对象销毁前显式调用 cleanup 方法
        except Exception as e:
            print(f"[MCP Error] 对象销毁时清理资源失败: {str(e)}")

    async def cleanup(self):
        """显式清理方法，应该在对象销毁前调用"""
        try:
            await self.disconnect_from_server()
            self._cached_tools = None
            self._connection_initialized = False
        except Exception as e:
            print(f"[MCP Error] 清理资源时发生错误: {str(e)}")

    async def reset_connection(self):
        """强制重置连接和工具缓存"""
        print("[MCP Debug] 强制重置连接和工具缓存")
        self._cached_tools = None
        self._connection_initialized = False
        await self.disconnect_from_server()
        # 立即重新连接确保可用性
        await self.connect_to_server()
        return await self.get_tool_list() 

    def _add_citations_from_tools(self, response: str, citations: list) -> dict:
        """处理包含工具调用结果的引用"""
        print(f"[Citation Debug] 开始处理引用 | 响应长度: {len(response)} | 引用数量: {len(citations)}")
        if not citations:
            print("[Citation Debug] 没有引用，返回空引用结构")
            return {"content": response, "reference": {"chunks": [], "doc_aggs": []}}
        
        # 构建引用数据结构
        chunks = []
        doc_aggs = []
        
        print("[Citation Debug] 开始处理每个引用:")
        for idx, citation in enumerate(citations):
            print(f"\n[Citation Debug] 处理第 {idx + 1} 个引用:")
            print(f"- doc_id: {citation.get('doc_id', 'None')}")
            print(f"- docnm_kwd: {citation.get('docnm_kwd', 'None')}")
            print(f"- content_ltks 长度: {len(citation.get('content_ltks', ''))}")
            
            # 跳过无效引用
            if not citation.get("content_ltks"):
                print("- 跳过：无效引用（没有content_ltks）")
                continue
                
            # 添加到chunks，确保包含所有必要字段
            chunk = {
                "doc_id": citation.get("doc_id", ""),
                "docnm_kwd": citation.get("docnm_kwd", ""),
                "content_ltks": citation.get("content_ltks", ""),
                "vector": citation.get("vector"),  # 确保包含vector字段，即使为None
            }
            chunks.append(chunk)
            print(f"- 已添加到chunks")
            
            # 添加到doc_aggs（去重）
            doc_agg = {
                "doc_id": citation.get("doc_id", ""),
                "doc_name": citation.get("docnm_kwd", "")
            }
            if doc_agg not in doc_aggs:
                doc_aggs.append(doc_agg)
                print(f"- 已添加到doc_aggs")
        
        # 处理引用标记
        modified_response = response
        try:
            modified_response, idx = settings.retrievaler.insert_citations(
                modified_response,
                [c["content_ltks"] for c in chunks],
                [c["vector"] if c["vector"] is not None else [0.0] * 1536 for c in chunks],  # 使用默认向量维度
                LLMBundle(self._canvas.get_tenant_id(), LLMType.EMBEDDING,
                        self._canvas.get_embedding_model()),
                tkweight=0.7,
                vtweight=0.3
            )
        except Exception as e:
            print(f"[Citation Debug] 引用处理失败: {str(e)}")
            # 如果处理失败，返回原始响应
            return {"content": response, "reference": {"chunks": [], "doc_aggs": []}}
        
        # 构建引用结构
        reference = {
            "chunks": chunks,
            "doc_aggs": doc_aggs
        }
        print(f"\n[Citation Debug] 引用结构构建完成:")
        print(f"- chunks数量: {len(chunks)}")
        print(f"- doc_aggs数量: {len(doc_aggs)}")
        
        # 构建最终返回结构
        result = {
            "content": modified_response,
            "reference": reference,
            "has_citation": True
        }
        print("\n[Citation Debug] 返回最终结构:")
        print(f"- content长度: {len(result['content'])}")
        print(f"- has_citation: {result['has_citation']}")
        print(f"- reference结构: {result['reference'].keys()}")
        
        # 使用structure_answer处理最终结构
        result = structure_answer(None, result, "", "")
        return result 

    def get_dependent_components(self):
        """获取依赖的组件列表"""
        inputs = self.get_input_elements()
        # 排除answer和begin开头的组件
        cpnts = set([i["key"] for i in inputs[1:] if i["key"].lower().find("answer") < 0 and i["key"].lower().find("begin") < 0])
        return list(cpnts)

    def get_input(self):
        print("\n[MCP Debug] 开始获取输入")
        # 在开头添加空值检查
        if not hasattr(self, '_canvas') or not self._canvas.path:
            return pd.DataFrame()

        # 初始化 upstream_outs 防止未定义
        upstream_outs = []  # 新增初始化
        
        # 在反向组件列表前添加空列表保护
        reversed_cpnts = []
        try:
            if len(self._canvas.path) > 1:
                reversed_cpnts.extend(self._canvas.path[-2])
            reversed_cpnts.extend(self._canvas.path[-1])
        except IndexError:
            pass

        # 修改断言为更友好的错误处理
        if not upstream_outs:  # 现在变量已确保初始化
            print("[MCP Debug] 警告: 未找到有效输入源，使用空输入")
            return pd.DataFrame([{"content": "未检测到有效输入"}])

        print(f"[MCP Debug] 组件路径: {self._canvas.path}")
        print(f"[MCP Debug] 反向组件列表: {reversed_cpnts}")

        if self._param.query:
            print("[MCP Debug] 处理查询参数")
            self._param.inputs = []
            outs = []
            for q in self._param.query:
                print(f"\n[MCP Debug] 处理查询项: {q}")
                if q.get("component_id"):
                    if q["component_id"].split("@")[0].lower().find("begin") >= 0:
                        cpn_id, key = q["component_id"].split("@")
                        print(f"[MCP Debug] 处理begin组件引用: {cpn_id}@{key}")
                        component = self._canvas.get_component(cpn_id)
                        if not component:
                            print(f"[MCP Debug] 警告: 未找到组件 {cpn_id}")
                            continue
                            
                        for p in component["obj"]._param.query:
                            if p["key"] == key:
                                print(f"[MCP Debug] 找到参数: {p}")
                                outs.append(pd.DataFrame([{"content": p.get("value", "")}]))
                                self._param.inputs.append({"component_id": q["component_id"],
                                                           "content": p.get("value", "")})
                                break
                        else:
                            print(f"[MCP Debug] 错误: 未找到参数 '{key}' for {cpn_id}")
                            assert False, f"Can't find parameter '{key}' for {cpn_id}"
                        continue

                    if q["component_id"].lower().find("answer") == 0:
                        print("[MCP Debug] 处理Answer组件引用")
                        txt = []
                        for r, c in self._canvas.history[::-1][:self._param.message_history_window_size][::-1]:
                            txt.append(f"{r.upper()}: {c}")
                        txt = "\n".join(txt)
                        print(f"[MCP Debug] Answer组件历史: {txt[:100]}...")
                        self._param.inputs.append({"content": txt, "component_id": q["component_id"]})
                        outs.append(pd.DataFrame([{"content": txt}]))
                        continue

                    print(f"[MCP Debug] 处理普通组件引用: {q['component_id']}")
                    component = self._canvas.get_component(q["component_id"])
                    if not component:
                        print(f"[MCP Debug] 警告: 未找到组件 {q['component_id']}")
                        continue
                        
                    out = component["obj"].output(allow_partial=False)[1]
                    print(f"[MCP Debug] 组件输出: {out}")
                    outs.append(out)
                    self._param.inputs.append({"component_id": q["component_id"],
                                               "content": "\n".join(
                                                   [str(d["content"]) for d in out.to_dict('records')])})
                elif q.get("value"):
                    print(f"[MCP Debug] 处理固定值: {q['value']}")
                    self._param.inputs.append({"component_id": None, "content": q["value"]})
                    outs.append(pd.DataFrame([{"content": q["value"]}]))
                    
            if outs:
                print("[MCP Debug] 合并所有输出")
                df = pd.concat(outs, ignore_index=True)
                if "content" in df:
                    df = df.drop_duplicates(subset=['content']).reset_index(drop=True)
                print(f"[MCP Debug] 最终输出: {df}")
                return df

        print("[MCP Debug] 处理上游组件输出")
        upstream_outs = []

        for u in reversed_cpnts[::-1]:
            print(f"\n[MCP Debug] 检查上游组件: {u}")
            if self.get_component_name(u) in ["switch", "concentrator"]:
                print(f"[MCP Debug] 跳过特殊组件: {u}")
                continue
                
            if self.component_name.lower() == "generate" and self.get_component_name(u) == "retrieval":
                print("[MCP Debug] 处理Generate组件的Retrieval输入")
                o = self._canvas.get_component(u)["obj"].output(allow_partial=False)[1]
                if o is not None:
                    o["component_id"] = u
                    upstream_outs.append(o)
                    print(f"[MCP Debug] 添加Retrieval输出: {o}")
                    continue
                    
            if self.component_name.lower().find("switch") < 0 \
                    and self.get_component_name(u) in ["relevant", "categorize"]:
                print(f"[MCP Debug] 跳过特定组件: {u}")
                continue
                
            if u.lower().find("answer") >= 0:
                print("[MCP Debug] 处理Answer组件历史")
                for r, c in self._canvas.history[::-1]:
                    if r == "user":
                        upstream_outs.append(pd.DataFrame([{"content": c, "component_id": u}]))
                        print(f"[MCP Debug] 添加用户历史: {c[:100]}...")
                        break
                break
                
            if self.component_name.lower().find("answer") >= 0 and self.get_component_name(u) in ["relevant"]:
                print(f"[MCP Debug] 跳过Answer组件的relevant输入")
                continue
                
            print(f"[MCP Debug] 获取组件输出: {u}")
            o = self._canvas.get_component(u)["obj"].output(allow_partial=False)[1]
            if o is not None:
                o["component_id"] = u
                upstream_outs.append(o)
                print(f"[MCP Debug] 添加组件输出: {o}")
            break

        if not upstream_outs:
            print("[MCP Debug] 警告: 未找到有效输入源，使用空输入")
            return pd.DataFrame([{"content": "未检测到有效输入"}])

        print("[MCP Debug] 合并上游输出")
        df = pd.concat(upstream_outs, ignore_index=True)
        if "content" in df:
            df = df.drop_duplicates(subset=['content']).reset_index(drop=True)
        print(f"[MCP Debug] 最终输出: {df}")

        self._param.inputs = []
        for _, r in df.iterrows():
            self._param.inputs.append({"component_id": r["component_id"], "content": r["content"]})
        print(f"[MCP Debug] 设置输入参数: {self._param.inputs}")

        return df
    
    