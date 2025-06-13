#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import os
import random
import xxhash
import traceback
from datetime import datetime

from api.db.db_utils import bulk_insert_into_db
from deepdoc.parser import PdfParser
from peewee import JOIN
from api.db.db_models import DB, File2Document, File
from api.db import StatusEnum, FileType, TaskStatus
from api.db.db_models import Task, Document, Knowledgebase, Tenant
from api.db.services.common_service import CommonService
from api.db.services.document_service import DocumentService
from api.utils import current_timestamp, get_uuid
from deepdoc.parser.excel_parser import RAGFlowExcelParser
from rag.settings import SVR_QUEUE_NAME
from rag.utils.storage_factory import STORAGE_IMPL
from rag.utils.redis_conn import REDIS_CONN
from api import settings
from rag.nlp import search
import logging

def write_debug_log(message: str, error: Exception = None):
    """
    将调试信息写入本地文件
    Args:
        message: 要记录的调试信息
        error: 异常对象（可选）
    """
    try:
        # 确保logs目录存在
        log_dir = os.path.join('/home/front/workspace/ragflow-main')
        
        # 日志文件路径
        log_file = os.path.join(log_dir, 'graphrag_debug.txt')
        
        # 获取当前时间戳
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 写入日志
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
            # 如果有错误对象，记录详细的错误信息
            if error:
                f.write("-" * 80 + "\n")
                f.write(f"Error Type: {type(error).__name__}\n")
                f.write(f"Error Message: {str(error)}\n")
                f.write("Traceback:\n")
                f.write(traceback.format_exc())
                f.write("-" * 80 + "\n")
            elif "[ERROR]" in message or "Exception" in message:
                f.write("-" * 80 + "\n")
                f.write(f"Error Message: {message}\n")
                f.write("Stack Trace:\n")
                f.write(traceback.format_stack()[-2])
                f.write("-" * 80 + "\n")
    except Exception as e:
        logging.error(f"Failed to write debug log: {str(e)}")

def trim_header_by_lines(text: str, max_length) -> str:
    len_text = len(text)
    if len_text <= max_length:
        return text
    for i in range(len_text):
        if text[i] == '\n' and len_text - i <= max_length:
            return text[i + 1:]
    return text


class TaskService(CommonService):
    model = Task

    @classmethod
    @DB.connection_context()
    def get_task(cls, task_id):
        """
        获取任务详细信息
        Args:
            cls: 类对象
            task_id: 任务ID
        Returns:
            任务详细信息字典或None（如果任务不存在或重试次数超过限制）
        """
        # 定义需要查询的字段列表
        fields = [
            cls.model.id,              # 任务ID
            cls.model.doc_id,          # 文档ID
            cls.model.from_page,       # 起始页码
            cls.model.to_page,         # 结束页码
            cls.model.retry_count,     # 重试次数
            Document.kb_id,            # 知识库ID
            Document.parser_id,        # 解析器ID
            Document.parser_config,    # 解析器配置
            Document.name,             # 文档名称
            Document.type,             # 文档类型
            Document.location,         # 文档位置
            Document.size,             # 文档大小
            Knowledgebase.tenant_id,   # 租户ID
            Knowledgebase.language,    # 语言设置
            Knowledgebase.embd_id,     # 嵌入模型ID
            Knowledgebase.pagerank,    # 页面排名
            Knowledgebase.parser_config.alias("kb_parser_config"),  # 知识库解析器配置
            Tenant.img2txt_id,         # 图片转文本模型ID
            Tenant.asr_id,             # 语音识别模型ID
            Tenant.llm_id,             # 语言模型ID
            cls.model.update_time,     # 更新时间
        ]

        # 构建多表联合查询
        docs = (
            cls.model.select(*fields)
                .join(Document, on=(cls.model.doc_id == Document.id))           # 关联文档表
                .join(Knowledgebase, on=(Document.kb_id == Knowledgebase.id))  # 关联知识库表
                .join(Tenant, on=(Knowledgebase.tenant_id == Tenant.id))       # 关联租户表
                .where(cls.model.id == task_id)                                # 指定任务ID
        )
        # 将查询结果转换为字典列表
        docs = list(docs.dicts())
        # 如果没有找到任务，返回None
        if not docs:
            return None

        # 生成任务接收时间的消息
        msg = f"\n{datetime.now().strftime('%H:%M:%S')} Task has been received."
        # 生成随机初始进度（0-10%）
        prog = random.random() / 10.0
        # 如果重试次数超过3次，标记为失败
        if docs[0]["retry_count"] >= 3:
            msg = "\nERROR: Task is abandoned after 3 times attempts."
            prog = -1

        # 更新任务状态
        cls.model.update(
            progress_msg=cls.model.progress_msg + msg,  # 追加进度消息
            progress=prog,                              # 更新进度
            retry_count=docs[0]["retry_count"] + 1,    # 增加重试次数
        ).where(cls.model.id == docs[0]["id"]).execute()

        # 如果重试次数超过限制，返回None
        if docs[0]["retry_count"] >= 3:
            return None

        # 返回任务详细信息
        return docs[0]

    @classmethod
    @DB.connection_context()
    def get_tasks(cls, doc_id: str):
        """
        获取指定文档的所有任务
        Args:
            doc_id: 文档ID
        Returns:
            任务列表，如果没有任务则返回None
        """
        # 定义需要查询的字段
        fields = [
            cls.model.id,          # 任务ID
            cls.model.from_page,   # 起始页码
            cls.model.progress,    # 任务进度
            cls.model.digest,      # 任务摘要
            cls.model.chunk_ids,   # 分块ID列表
        ]
        # 查询任务并按起始页码升序和创建时间降序排序
        tasks = (
            cls.model.select(*fields).order_by(cls.model.from_page.asc(), cls.model.create_time.desc())
                .where(cls.model.doc_id == doc_id)
        )
        # 将查询结果转换为字典列表
        tasks = list(tasks.dicts())
        if not tasks:
            return None
        return tasks

    @classmethod
    @DB.connection_context()
    def update_chunk_ids(cls, id: str, chunk_ids: str):
        """
        更新任务的chunk_ids
        Args:
            id: 任务ID
            chunk_ids: 新的chunk_ids字符串
        """
        # 更新指定任务的chunk_ids字段
        cls.model.update(chunk_ids=chunk_ids).where(cls.model.id == id).execute()

    @classmethod
    @DB.connection_context()
    def get_ongoing_doc_name(cls):
        """
        获取正在处理的文档名称列表
        Returns:
            包含文档ID和位置的元组列表
        """
        # 使用数据库锁确保并发安全
        with DB.lock("get_task", -1):
            # 查询正在处理的任务相关信息
            docs = (
                cls.model.select(
                    *[Document.id, Document.kb_id, Document.location, File.parent_id]
                )
                    .join(Document, on=(cls.model.doc_id == Document.id))
                    .join(
                    File2Document,
                    on=(File2Document.document_id == Document.id),
                    join_type=JOIN.LEFT_OUTER,
                )
                    .join(
                    File,
                    on=(File2Document.file_id == File.id),
                    join_type=JOIN.LEFT_OUTER,
                )
                    .where(
                    Document.status == StatusEnum.VALID.value,        # 文档状态有效
                    Document.run == TaskStatus.RUNNING.value,         # 文档正在运行
                    ~(Document.type == FileType.VIRTUAL.value),       # 不是虚拟文档
                    cls.model.progress < 1,                          # 任务未完成
                    cls.model.create_time >= current_timestamp() - 1000 * 600,  # 最近10分钟内创建的任务
                )
            )
            # 将查询结果转换为字典列表
            docs = list(docs.dicts())
            if not docs:
                return []

            # 返回去重后的文档ID和位置列表
            return list(
                set(
                    [
                        (
                            d["parent_id"] if d["parent_id"] else d["kb_id"],  # 优先使用父ID，否则使用知识库ID
                            d["location"],                                     # 文档位置
                        )
                        for d in docs
                    ]
                )
            )

    @classmethod
    @DB.connection_context()
    def do_cancel(cls, id):
        """
        检查任务是否应该被取消
        Args:
            id: 任务ID
        Returns:
            如果文档已取消或进度小于0则返回True
        """
        # 获取任务和关联的文档信息
        task = cls.model.get_by_id(id)
        _, doc = DocumentService.get_by_id(task.doc_id)
        # 检查文档是否已取消或进度小于0
        return doc.run == TaskStatus.CANCEL.value or doc.progress < 0

    @classmethod
    @DB.connection_context()
    def update_progress(cls, id, info):
        """
        更新任务进度信息
        Args:
            id: 任务ID
            info: 包含进度信息的字典
        """
        # 如果是MacOS环境，直接更新进度
        if os.environ.get("MACOS"):
            if info["progress_msg"]:
                # 获取任务并更新进度消息
                task = cls.model.get_by_id(id)
                progress_msg = trim_header_by_lines(task.progress_msg + "\n" + info["progress_msg"], 3000)
                cls.model.update(progress_msg=progress_msg).where(cls.model.id == id).execute()
            if "progress" in info:
                # 更新进度值
                cls.model.update(progress=info["progress"]).where(
                    cls.model.id == id
                ).execute()
            return

        # 其他环境使用数据库锁确保并发安全
        with DB.lock("update_progress", -1):
            if info["progress_msg"]:
                # 获取任务并更新进度消息
                task = cls.model.get_by_id(id)
                progress_msg = trim_header_by_lines(task.progress_msg + "\n" + info["progress_msg"], 3000)
                cls.model.update(progress_msg=progress_msg).where(cls.model.id == id).execute()
            if "progress" in info:
                # 更新进度值
                cls.model.update(progress=info["progress"]).where(
                    cls.model.id == id
                ).execute()


def handle_llm_error(error: Exception, task_id: str, retry_count: int = 0):
    """
    处理LLM调用错误
    Args:
        error: 异常对象
        task_id: 任务ID
        retry_count: 当前重试次数
    """
    error_message = f"[ERROR] LLM error for task {task_id}: {str(error)}"
    write_debug_log(error_message, error)
    
    # 如果是内容不适当的错误，记录详细信息
    if "Output data may contain inappropriate content" in str(error):
        write_debug_log(f"[WARNING] Content validation failed for task {task_id}")
    
    # 如果是重试次数超过限制，标记任务为失败
    if retry_count >= 3:
        DocumentService.update_by_id(task_id, {
            "run": TaskStatus.FAILED.value,
            "progress_msg": f"LLM error after {retry_count} retries: {str(error)}"
        })
        raise Exception(f"LLM error after {retry_count} retries: {str(error)}")
    
    return retry_count + 1

def queue_tasks(doc: dict, bucket: str, name: str):
    """
    将文档处理任务加入队列
    Args:
        doc: 文档信息字典
        bucket: 存储桶名称
        name: 文件名
    """
    try:
        def new_task():
            # 创建新的任务字典，包含任务ID、文档ID、进度和页面范围
            return {"id": get_uuid(), "doc_id": doc["id"], "progress": 0.0, "from_page": 0, "to_page": 100000000}

        parse_task_array = []
        debug_message = f"[DEBUG] Starting task queue for document: {doc['id']}"
        print(debug_message)
        write_debug_log(debug_message)

        if doc["type"] == FileType.PDF.value:
            # 处理PDF文档
            file_bin = STORAGE_IMPL.get(bucket, name)  # 从存储中获取PDF文件内容
            do_layout = doc["parser_config"].get("layout_recognize", "DeepDOC")  # 获取布局识别配置
            pages = PdfParser.total_page_number(doc["name"], file_bin)  # 获取PDF总页数
            page_size = doc["parser_config"].get("task_page_size", 12)  # 获取每个任务处理的页面数量
            
            # 根据不同的解析器类型调整页面大小
            if doc["parser_id"] == "paper":
                page_size = doc["parser_config"].get("task_page_size", 22)
            if doc["parser_id"] in ["one", "knowledge_graph"] or do_layout != "DeepDOC":
                page_size = 10 ** 9  # 对于特定类型，将所有页面作为一个任务处理
            
            # 获取需要处理的页面范围，默认处理所有页面
            page_ranges = doc["parser_config"].get("pages") or [(1, 10 ** 5)]
            
            # 根据页面范围创建任务
            for s, e in page_ranges:
                s -= 1  # 转换为0基页码
                s = max(0, s)  # 确保起始页不小于0
                e = min(e - 1, pages)  # 确保结束页不超过总页数
                # 按照page_size大小分割任务
                for p in range(s, e, page_size):
                    task = new_task()
                    task["from_page"] = p
                    task["to_page"] = min(p + page_size, e)
                    parse_task_array.append(task)

        elif doc["parser_id"] == "table":
            # 处理表格文档
            file_bin = STORAGE_IMPL.get(bucket, name)  # 获取表格文件内容
            rn = RAGFlowExcelParser.row_number(doc["name"], file_bin)  # 获取表格总行数
            # 每3000行创建一个任务
            for i in range(0, rn, 3000):
                task = new_task()
                task["from_page"] = i
                task["to_page"] = min(i + 3000, rn)
                parse_task_array.append(task)
        else:
            # 其他类型文档，创建单个任务
            parse_task_array.append(new_task())

        # 获取文档的分块配置
        chunking_config = DocumentService.get_chunking_config(doc["id"])
        
        # 为每个任务计算唯一摘要，用于后续任务复用判断
        for task in parse_task_array:
            hasher = xxhash.xxh64()
            # 将配置信息加入摘要计算
            for field in sorted(chunking_config.keys()):
                if field == "parser_config":
                    # 移除特定配置项，避免影响摘要计算
                    for k in ["raptor", "graphrag"]:
                        if k in chunking_config[field]:
                            del chunking_config[field][k]
                hasher.update(str(chunking_config[field]).encode("utf-8"))
            # 将任务相关信息加入摘要计算
            for field in ["doc_id", "from_page", "to_page"]:
                hasher.update(str(task.get(field, "")).encode("utf-8"))
            task_digest = hasher.hexdigest()
            task["digest"] = task_digest
            task["progress"] = 0.0

        # 获取之前的任务列表
        prev_tasks = TaskService.get_tasks(doc["id"])
        ck_num = 0
        if prev_tasks:
            # 尝试复用之前任务的处理结果
            for task in parse_task_array:
                ck_num += reuse_prev_task_chunks(task, prev_tasks, chunking_config)
            # 删除旧的任务记录
            TaskService.filter_delete([Task.doc_id == doc["id"]])
            # 收集所有chunk_ids
            chunk_ids = []
            for task in prev_tasks:
                if task["chunk_ids"]:
                    chunk_ids.extend(task["chunk_ids"].split())
            # 删除旧的chunks
            if chunk_ids:
                settings.docStoreConn.delete({"id": chunk_ids}, search.index_name(chunking_config["tenant_id"]),
                                            chunking_config["kb_id"])
        # 更新文档的chunk数量
        DocumentService.update_by_id(doc["id"], {"chunk_num": ck_num})

        # 将新任务批量插入数据库
        bulk_insert_into_db(Task, parse_task_array, True)
        # 开始文档解析
        DocumentService.begin2parse(doc["id"])

        # 获取所有未完成的任务
        unfinished_task_array = [task for task in parse_task_array if task["progress"] < 1.0]
        # 将未完成的任务放入Redis队列
        for unfinished_task in unfinished_task_array:
            try:
                if not REDIS_CONN.queue_product(SVR_QUEUE_NAME, message=unfinished_task):
                    raise Exception("Can't access Redis. Please check the Redis' status.")
            except Exception as e:
                # Redis错误处理
                DocumentService.update_by_id(doc["id"], {
                    "run": TaskStatus.FAILED.value,
                    "progress_msg": f"Redis error: {str(e)}"
                })
                raise

    except Exception as e:
        # 增强错误日志记录
        write_debug_log(f"[ERROR] Task queue error", error=e)
        # 全局错误处理
        DocumentService.update_by_id(doc["id"], {
            "run": TaskStatus.FAILED.value,
            "progress_msg": f"Task queue error: {str(e)}"   
        })
        raise


def reuse_prev_task_chunks(task: dict, prev_tasks: list[dict], chunking_config: dict):
    """
    尝试复用之前任务的chunks
    Args:
        task: 当前任务
        prev_tasks: 之前的任务列表
        chunking_config: 分块配置
    Returns:
        复用的chunk数量
    """
    # 查找匹配的之前任务
    idx = 0
    while idx < len(prev_tasks):
        prev_task = prev_tasks[idx]
        if prev_task.get("from_page", 0) == task.get("from_page", 0) \
                and prev_task.get("digest", 0) == task.get("digest", ""):
            break
        idx += 1

    # 如果没找到匹配的任务，或任务未完成，或没有chunks，返回0
    if idx >= len(prev_tasks):
        return 0
    prev_task = prev_tasks[idx]
    if prev_task["progress"] < 1.0 or not prev_task["chunk_ids"]:
        return 0
    
    # 复用chunks
    task["chunk_ids"] = prev_task["chunk_ids"]
    task["progress"] = 1.0
    # 设置进度消息
    if "from_page" in task and "to_page" in task and int(task['to_page']) - int(task['from_page']) >= 10 ** 6:
        task["progress_msg"] = f"Page({task['from_page']}~{task['to_page']}): "
    else:
        task["progress_msg"] = ""
    task["progress_msg"] = " ".join(
        [datetime.now().strftime("%H:%M:%S"), task["progress_msg"], "Reused previous task's chunks."])
    prev_task["chunk_ids"] = ""

    return len(task["chunk_ids"].split())
