# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License
"""
Reference:
 - [graphrag](https://github.com/microsoft/graphrag)
"""
import re
from typing import Any, Callable
from dataclasses import dataclass
from graphrag.general.extractor import Extractor, ENTITY_EXTRACTION_MAX_GLEANINGS
from graphrag.light.graph_prompt import PROMPTS
from graphrag.utils import pack_user_ass_to_openai_messages, split_string_by_multi_markers, chat_limiter
from rag.llm.chat_model import Base as CompletionLLM
import networkx as nx
from rag.utils import num_tokens_from_string
import trio
import logging
import os
from datetime import datetime
from timeit import default_timer as timer
from api.db.services.task_service import handle_llm_error


@dataclass
class GraphExtractionResult:
    """Unipartite graph extraction result class definition."""

    output: nx.Graph
    source_docs: dict[Any, Any]


class GraphExtractor(Extractor):

    _max_gleanings: int
    task_id: str = None  # Add task_id attribute

    def __init__(
        self,
        llm_invoker: CompletionLLM,
        language: str | None = "English",
        entity_types: list[str] | None = None,
        get_entity: Callable | None = None,
        set_entity: Callable | None = None,
        get_relation: Callable | None = None,
        set_relation: Callable | None = None,
        example_number: int = 2,
        max_gleanings: int | None = None,
        task_id: str = None,  # Add task_id parameter
    ):
        super().__init__(llm_invoker, language, entity_types, get_entity, set_entity, get_relation, set_relation)
        """Init method definition."""
        self._max_gleanings = (
            max_gleanings
            if max_gleanings is not None
            else ENTITY_EXTRACTION_MAX_GLEANINGS
        )
        self._example_number = example_number
        self.task_id = task_id  # Set task_id
        examples = "\n".join(
                PROMPTS["entity_extraction_examples"][: int(self._example_number)]
            )

        example_context_base = dict(
            tuple_delimiter=PROMPTS["DEFAULT_TUPLE_DELIMITER"],
            record_delimiter=PROMPTS["DEFAULT_RECORD_DELIMITER"],
            completion_delimiter=PROMPTS["DEFAULT_COMPLETION_DELIMITER"],
            entity_types=",".join(self._entity_types),
            language=self._language,
        )
        # add example's format
        examples = examples.format(**example_context_base)

        self._entity_extract_prompt = PROMPTS["entity_extraction"]
        self._context_base = dict(
            tuple_delimiter=PROMPTS["DEFAULT_TUPLE_DELIMITER"],
            record_delimiter=PROMPTS["DEFAULT_RECORD_DELIMITER"],
            completion_delimiter=PROMPTS["DEFAULT_COMPLETION_DELIMITER"],
            entity_types=",".join(self._entity_types),
            examples=examples,
            language=self._language,
        )

        self._continue_prompt = PROMPTS["entiti_continue_extraction"]
        self._if_loop_prompt = PROMPTS["entiti_if_loop_extraction"]

        self._left_token_count = llm_invoker.max_length - num_tokens_from_string(
            self._entity_extract_prompt.format(
                **self._context_base, input_text="{input_text}"
            ).format(**self._context_base, input_text="")
        )
        self._left_token_count = max(llm_invoker.max_length * 0.6, self._left_token_count)

    async def _process_single_content(self, chunk_key_dp: tuple[str, str], chunk_seq: int, num_chunks: int, out_results):
        def write_debug_log(message: str):
            """
            将调试信息写入本地文件
            Args:
                message: 要记录的调试信息
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
            except Exception as e:
                logging.error(f"Failed to write debug log: {str(e)}")

        token_count = 0
        chunk_key = chunk_key_dp[0]
        content = chunk_key_dp[1]
        hint_prompt = self._entity_extract_prompt.format(
            **self._context_base, input_text="{input_text}"
        ).format(**self._context_base, input_text=content)

        # -----DEBUG LLM进度-----
        debug_message = f"[DEBUG] Processing chunk {chunk_seq}/{num_chunks}"
        print(debug_message)
        write_debug_log(debug_message)
        debug_message = f"[DEBUG] Chunk size: {len(content)} characters"
        print(debug_message)
        write_debug_log(debug_message)

        retry_count = 0
        while True:
            try:
                llm_start = timer()
                gen_conf = {
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "top_p": 0.95,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                    "stop": None
                }
                async with chat_limiter:
                    debug_message = f"[DEBUG] Starting LLM call for chunk {chunk_seq}"
                    print(debug_message)
                    write_debug_log(debug_message)
                    final_result = await trio.to_thread.run_sync(lambda: self._chat(hint_prompt, [{"role": "user", "content": "Output:"}], gen_conf))
                token_count += num_tokens_from_string(hint_prompt + final_result)
                history = pack_user_ass_to_openai_messages("Output:", final_result, self._continue_prompt)
                for now_glean_index in range(self._max_gleanings):
                    async with chat_limiter:
                        glean_result = await trio.to_thread.run_sync(lambda: self._chat(hint_prompt, history, gen_conf))
                    history.extend([{"role": "assistant", "content": glean_result}, {"role": "user", "content": self._continue_prompt}])
                    token_count += num_tokens_from_string("\n".join([m["content"] for m in history]) + hint_prompt + self._continue_prompt)
                    final_result += glean_result
                    if now_glean_index == self._max_gleanings - 1:
                        break

                    async with chat_limiter:
                        if_loop_result = await trio.to_thread.run_sync(lambda: self._chat(self._if_loop_prompt, history, gen_conf))
                    token_count += num_tokens_from_string("\n".join([m["content"] for m in history]) + if_loop_result + self._if_loop_prompt)
                    if_loop_result = if_loop_result.strip().strip('"').strip("'").lower()
                    if if_loop_result != "yes":
                        break

                records = split_string_by_multi_markers(
                    final_result,
                    [self._context_base["record_delimiter"], self._context_base["completion_delimiter"]],
                )
                llm_time = timer() - llm_start
                debug_message = f"[DEBUG] LLM call completed in {llm_time:.2f}s"
                print(debug_message)
                write_debug_log(debug_message)
                debug_message = f"[DEBUG] LLM response size: {len(final_result)} characters"
                print(debug_message)
                write_debug_log(debug_message)
                rcds = []
                for record in records:
                    record = re.search(r"\((.*)\)", record)
                    if record is None:
                        continue
                    rcds.append(record.group(1))
                records = rcds
                maybe_nodes, maybe_edges = self._entities_and_relations(chunk_key, records, self._context_base["tuple_delimiter"])
                out_results.append((maybe_nodes, maybe_edges, token_count))
                if self.callback:
                    self.callback(0.5+0.1*len(out_results)/num_chunks, msg = f"Entities extraction of chunk {chunk_seq} {len(out_results)}/{num_chunks} done, {len(maybe_nodes)} nodes, {len(maybe_edges)} edges, {token_count} tokens.")
                return maybe_nodes, maybe_edges, token_count
                
            except Exception as e:
                error_msg = str(e)
                if "Output data may contain inappropriate content" in error_msg:
                    # 记录原始错误信息
                    write_debug_log(f"[WARNING] Original error for chunk {chunk_seq}: {error_msg}")
                    
                    # 尝试清理输入内容
                    content = re.sub(r'[^\w\s\u4e00-\u9fff,.!?;，。！？；]', '', content)
                    # 移除特殊分隔符
                    content = content.replace("<|>", "").replace("##", "").replace("<|COMPLETE|>", "")
                    # 移除可能导致问题的关键词
                    content = content.replace("relationship", "relation")
                    
                    hint_prompt = self._entity_extract_prompt.format(
                        **self._context_base, input_text="{input_text}"
                    ).format(**self._context_base, input_text=content)
                    
                    retry_count += 1
                    if retry_count >= 3:
                        write_debug_log(f"[ERROR] Content validation failed after {retry_count} retries for chunk {chunk_seq}")
                        if len(out_results) > 0:
                            # 如果已经处理了一些块，返回空结果而不是失败
                            write_debug_log(f"[INFO] Skipping problematic chunk {chunk_seq} and continuing with {len(out_results)} processed chunks")
                            return {}, {}, 0
                        raise
                    
                    write_debug_log(f"[INFO] Retrying chunk {chunk_seq} after content cleaning (attempt {retry_count})")
                    await trio.sleep(1)
                    continue
                
                # 处理其他错误
                if hasattr(self, 'task_id'):
                    retry_count = handle_llm_error(e, self.task_id, retry_count)
                else:
                    write_debug_log(f"[ERROR] Error processing chunk {chunk_seq}: {str(e)}")
                    retry_count += 1
                
                if retry_count >= 3:
                    write_debug_log(f"[ERROR] Max retries reached for chunk {chunk_seq}")
                    if len(out_results) > 0:
                        # 如果已经处理了一些块，返回空结果而不是失败
                        write_debug_log(f"[INFO] Skipping problematic chunk {chunk_seq} and continuing with {len(out_results)} processed chunks")
                        return {}, {}, 0
                    raise
                
                await trio.sleep(1)
                continue
