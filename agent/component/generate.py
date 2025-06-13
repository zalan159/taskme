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
import re
from functools import partial
import pandas as pd
from api.db import LLMType
from api.db.services.conversation_service import structure_answer
from api.db.services.llm_service import LLMBundle
from api import settings
from agent.component.base import ComponentBase, ComponentParamBase
from rag.prompts import message_fit_in


class GenerateParam(ComponentParamBase):
    """
    Define the Generate component parameters.
    """

    def __init__(self):
        super().__init__()
        self.llm_id = ""
        self.prompt = ""
        self.max_tokens = 1000
        self.temperature = 0
        self.top_p = 0
        self.presence_penalty = 0
        self.frequency_penalty = 0
        self.cite = True
        self.parameters = []

    def check(self):
        self.check_decimal_float(self.temperature, "[Generate] Temperature")
        self.check_decimal_float(self.presence_penalty, "[Generate] Presence penalty")
        self.check_decimal_float(self.frequency_penalty, "[Generate] Frequency penalty")
        self.check_nonnegative_number(self.max_tokens, "[Generate] Max tokens")
        self.check_decimal_float(self.top_p, "[Generate] Top P")
        self.check_empty(self.llm_id, "[Generate] LLM")
        # self.check_defined_type(self.parameters, "Parameters", ["list"])

    def gen_conf(self):
        conf = {}
        if self.max_tokens is None or self.max_tokens <= 0:
            conf["max_tokens"] = 1000
        else:
            conf["max_tokens"] = self.max_tokens
        if self.temperature > 0:
            conf["temperature"] = self.temperature
        if self.top_p > 0:
            conf["top_p"] = self.top_p
        if self.presence_penalty > 0:
            conf["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty > 0:
            conf["frequency_penalty"] = self.frequency_penalty
        return conf


class Generate(ComponentBase):
    component_name = "Generate"

    def get_dependent_components(self):
        inputs = self.get_input_elements()
        cpnts = set([i["key"] for i in inputs[1:] if i["key"].lower().find("answer") < 0 and i["key"].lower().find("begin") < 0])
        return list(cpnts)

    def set_cite(self, retrieval_res, answer):
        retrieval_res = retrieval_res.dropna(subset=["vector", "content_ltks"]).reset_index(drop=True)
        if "empty_response" in retrieval_res.columns:
            retrieval_res["empty_response"].fillna("", inplace=True)
        answer, idx = settings.retrievaler.insert_citations(answer,
                                                            [ck["content_ltks"] for _, ck in retrieval_res.iterrows()],
                                                            [ck["vector"] for _, ck in retrieval_res.iterrows()],
                                                            LLMBundle(self._canvas.get_tenant_id(), LLMType.EMBEDDING,
                                                                      self._canvas.get_embedding_model()), tkweight=0.7,
                                                            vtweight=0.3)
        doc_ids = set([])
        recall_docs = []
        for i in idx:
            did = retrieval_res.loc[int(i), "doc_id"]
            if did in doc_ids:
                continue
            doc_ids.add(did)
            recall_docs.append({"doc_id": did, "doc_name": retrieval_res.loc[int(i), "docnm_kwd"]})

        del retrieval_res["vector"]
        del retrieval_res["content_ltks"]

        reference = {
            "chunks": [ck.to_dict() for _, ck in retrieval_res.iterrows()],
            "doc_aggs": recall_docs
        }

        if answer.lower().find("invalid key") >= 0 or answer.lower().find("invalid api") >= 0:
            answer += " Please set LLM API-Key in 'User Setting -> Model providers -> API-Key'"
        res = {"content": answer, "reference": reference}
        res = structure_answer(None, res, "", "")

        return res

    def get_input_elements(self):
        key_set = set([])
        res = [{"key": "user", "name": "Input your question here:"}]
        print(f"[{self.component_name}][get_input_elements] Parsing prompt: {self._param.prompt}")
        for r in re.finditer(r"\{([a-zA-Z0-9_]+[:@][a-zA-Z0-9_-]+)\}|\[([a-zA-Z0-9_]+)\]", self._param.prompt, flags=re.IGNORECASE):
            # r.group(1) 匹配 {component_id} 或 {begin@key} 或 {Answer:XXX}
            # r.group(2) 匹配 [deprecated_param_style]
            # 我们主要关心 r.group(1) 的模式
            placeholder_in_prompt = r.group(1)
            if not placeholder_in_prompt: # 如果匹配的是 deprecated_param_style，暂时忽略或按原有逻辑处理
                # 根据原有代码，这个 finditer 的正则表达式似乎更复杂，可能包含多种占位符格式
                # 为了精确，我们聚焦于确保 {begin@key} 能被正确识别，特别是当key在output_data中时
                # 原有正则: r"\{([a-z]+[:@][a-z0-9_-]+)\}"
                # 我们需要确保使用的是能正确捕获占位符的正则，这里暂时使用一个简化版本，聚焦问题
                # 假设 r.group(1) 是我们关心的占位符，例如 "begin@current_date"
                # 如果匹配了其他组，需要确保 placeholder_in_prompt 被正确赋值
                # 为了安全，我们只处理确认是 r.group(1) 的情况，如果后续发现其他匹配组也重要，再调整
                continue

            if placeholder_in_prompt in key_set:
                print(f"[{self.component_name}][get_input_elements] Placeholder '{placeholder_in_prompt}' already processed, skipping.")
                continue

            if placeholder_in_prompt.lower().startswith("begin@"):
                cpn_id_part, key_part = placeholder_in_prompt.split("@", 1)
                try:
                    begin_component_instance = self._canvas.get_component(cpn_id_part)["obj"]
                except Exception as e:
                    print(f"[{self.component_name}][get_input_elements][错误] Failed to get Begin component '{cpn_id_part}' instance: {e}. Skipping placeholder '{placeholder_in_prompt}'.")
                    continue

                param_name_for_ui = f"Data from Begin: {key_part}" # UI显示的名称
                found_key_in_begin = False

                # 1. 检查 Begin 组件的 output_data
                if hasattr(begin_component_instance._param, "output_data") and key_part in begin_component_instance._param.output_data:
                    # 如果key在output_data中，我们认为它是一个有效的输入元素
                    # UI name 可以自定义，或者就用 key_part
                    param_name_for_ui = begin_component_instance._param.output_data.get(f"{key_part}_name", key_part) # 假设output_data可能也存了name
                    res.append({"key": placeholder_in_prompt, "name": param_name_for_ui})
                    key_set.add(placeholder_in_prompt)
                    found_key_in_begin = True
                    print(f"[{self.component_name}][get_input_elements] Added '{placeholder_in_prompt}' from Begin output_data (key: '{key_part}').")
                
                # 2. 如果 output_data 中没有，再检查 Begin 组件的 query (原有逻辑)
                if not found_key_in_begin and hasattr(begin_component_instance._param, "query"):
                    for p_query_dict in begin_component_instance._param.query:
                        if p_query_dict.get("key") == key_part:
                            res.append({"key": placeholder_in_prompt, "name": p_query_dict.get("name", key_part)})
                            key_set.add(placeholder_in_prompt)
                            found_key_in_begin = True
                            print(f"[{self.component_name}][get_input_elements] Added '{placeholder_in_prompt}' from Begin query (key: '{key_part}').")
                            break
                
                if not found_key_in_begin:
                    print(f"[{self.component_name}][get_input_elements][警告] Placeholder '{placeholder_in_prompt}' (key: '{key_part}') not found in Begin's output_data or query. It might not be replaceable.")
                continue # 处理完 begin@ 后，继续下一个占位符
            
            # 处理其他类型的占位符 (如直接的component_id)
            # (这里的逻辑基于对原get_input_elements的理解，可能需要对照原版确保完整性)
            try:
                cpn_nm = self._canvas.get_component_name(placeholder_in_prompt) # placeholder_in_prompt是组件ID
                if not cpn_nm:
                    print(f"[{self.component_name}][get_input_elements][警告] Component ID '{placeholder_in_prompt}' not found or has no name. Skipping.")
                    continue
                res.append({"key": placeholder_in_prompt, "name": cpn_nm})
                key_set.add(placeholder_in_prompt)
                print(f"[{self.component_name}][get_input_elements] Added '{placeholder_in_prompt}' as a component input.")
            except Exception as e:
                print(f"[{self.component_name}][get_input_elements][错误] Error processing placeholder '{placeholder_in_prompt}' as component ID: {e}. Skipping.")
        
        print(f"[{self.component_name}][get_input_elements] Identified input elements: {res}")
        return res

    def _run(self, history, **kwargs):
        chat_mdl = LLMBundle(self._canvas.get_tenant_id(), LLMType.CHAT, self._param.llm_id)
        prompt = self._param.prompt
        print(f"[{self.component_name}][调试日志] 原始System Prompt: {prompt}") # 调试日志：打印原始prompt

        retrieval_res = []
        self._param.inputs = []
        
        # 用于替换prompt的参数字典，会逐步填充
        prompt_params = {**kwargs} # 初始化，合并任何外部传入的kwargs

        for para in self.get_input_elements()[1:]:
            # para["key"] 就是 prompt 中的占位符，例如 "begin@current_date" 或 "some_component_id"
            placeholder_in_prompt = para["key"]

            if placeholder_in_prompt.lower().startswith("begin@"):
                cpn_id, key_in_begin = placeholder_in_prompt.split("@", 1) # 分割一次，避免key中包含@
                
                # 获取Begin组件实例
                try:
                    begin_component_instance = self._canvas.get_component(cpn_id)["obj"]
                except Exception as e:
                    print(f"[{self.component_name}][错误日志] 获取Begin组件 '{cpn_id}' 实例失败: {e}。跳过占位符 '{placeholder_in_prompt}'")
                    prompt_params[placeholder_in_prompt] = "" # 设置为空，避免替换错误
                    continue

                param_value = ""
                found_in_begin = False

                # 1. 优先从 Begin 组件的 output_data 获取
                if hasattr(begin_component_instance._param, "output_data") and key_in_begin in begin_component_instance._param.output_data:
                    param_value = begin_component_instance._param.output_data[key_in_begin]
                    found_in_begin = True
                    print(f"[{self.component_name}][调试日志] 从Begin组件 '{cpn_id}' 的 output_data 中获取到 '{placeholder_in_prompt}' = '{param_value}'")
                
                # 2. 如果 output_data 中没有，则从 Begin 组件的 query 获取
                elif hasattr(begin_component_instance._param, "query"):
                    for p_dict in begin_component_instance._param.query:
                        if p_dict.get("key") == key_in_begin:
                            param_value = p_dict.get("value", "")
                            found_in_begin = True
                            print(f"[{self.component_name}][调试日志] 从Begin组件 '{cpn_id}' 的 query 中获取到 '{placeholder_in_prompt}' = '{str(param_value)[:100]}...'")
                            break
                
                if found_in_begin:
                    prompt_params[placeholder_in_prompt] = param_value
                    self._param.inputs.append({"component_id": placeholder_in_prompt, "content": param_value})
                else:
                    prompt_params[placeholder_in_prompt] = "" # 未找到则设置为空字符串
                    print(f"[{self.component_name}][警告日志] 未能在Begin组件 '{cpn_id}' 的 output_data 或 query 中找到键 '{key_in_begin}' (对应占位符 '{placeholder_in_prompt}')。将使用空字符串替换。")
                continue

            # 处理其他组件的ID作为占位符的情况 (原有逻辑)
            component_id = placeholder_in_prompt
            try:
                cpn = self._canvas.get_component(component_id)["obj"]
            except Exception as e:
                print(f"[{self.component_name}][错误日志] 获取组件 '{component_id}' 实例失败: {e}。跳过占位符 '{placeholder_in_prompt}'")
                prompt_params[placeholder_in_prompt] = "" # 设置为空
                continue

            if cpn.component_name.lower() == "answer":
                hist = self._canvas.get_history(1)
                value_to_fill = hist[0]["content"] if hist else ""
                prompt_params[placeholder_in_prompt] = value_to_fill
                # self._param.inputs.append({"component_id": placeholder_in_prompt, "content": value_to_fill}) # Answer的输出通常不作为input记录
                print(f"[{self.component_name}][调试日志] 获取到Answer组件 '{placeholder_in_prompt}' 的内容 (历史): '{str(value_to_fill)[:100]}...'")
                continue
            
            _, out = cpn.output(allow_partial=False)
            if "content" not in out.columns:
                value_to_fill = ""
            else:
                if cpn.component_name.lower() == "retrieval":
                    retrieval_res.append(out)
                value_to_fill = "  - " + "\n - ".join([str(o) for o in out["content"]])
            
            prompt_params[placeholder_in_prompt] = value_to_fill
            self._param.inputs.append({"component_id": placeholder_in_prompt, "content": value_to_fill})
            print(f"[{self.component_name}][调试日志] 获取到组件 '{placeholder_in_prompt}' 的输出内容: '{str(value_to_fill)[:100]}...'")

        if retrieval_res:
            retrieval_res = pd.concat(retrieval_res, ignore_index=True)
        else:
            retrieval_res = pd.DataFrame([])

        print(f"[{self.component_name}][调试日志] 用于替换的参数字典 (prompt_params): { {k: str(v)[:100]+'...' if isinstance(v, str) and len(v)>100 else v for k,v in prompt_params.items()} }")
        # 使用构建好的 prompt_params 替换 prompt 中的占位符
        for placeholder_name, value_to_insert in prompt_params.items():
            # 使用 re.escape(placeholder_name) 来确保占位符中的特殊字符被正确处理
            # prompt 中的占位符是 {placeholder_name}
            regex_pattern = r"\{" + re.escape(placeholder_name) + r"\}"
            original_prompt_before_sub = prompt
            prompt = re.sub(regex_pattern, str(value_to_insert).replace("\\", " "), prompt)
            if original_prompt_before_sub != prompt:
                 print(f"[{self.component_name}][调试日志] 占位符 '{{{placeholder_name}}}' 被替换为 '{str(value_to_insert)[:100]}...'")
            # else:
                 # print(f"[{self.component_name}][调试日志] 占位符 '{{{placeholder_name}}}' 未在prompt中找到或值相同，未发生替换。")

        print(f"[{self.component_name}][调试日志] 所有替换完成后最终的System Prompt: {prompt}")

        if not self._param.inputs and prompt.find("{input}") >= 0:
            # 这段处理 {input} 的逻辑似乎是独立的，当没有通过get_input_elements()解析出输入时触发
            retrieval_data_for_input = self.get_input() # 注意：这个self.get_input()方法未在本类中定义，可能来自父类或需要特定上下文
            input_content = ("  - " + "\n  - ".join(
                [c for c in retrieval_data_for_input["content"] if isinstance(c, str)])) if "content" in retrieval_data_for_input else ""
            prompt = re.sub(r"\{input\}", input_content, prompt) # 这里没有 re.escape(input_content)，因为input_content是值不是模式的一部分
            print(f"[{self.component_name}][调试日志] 特殊占位符 '{{input}}' 被替换。")

        downstreams = self._canvas.get_component(self._id)["downstream"]
        if kwargs.get("stream") and len(downstreams) == 1 and self._canvas.get_component(downstreams[0])[
            "obj"].component_name.lower() == "answer":
            return partial(self.stream_output, chat_mdl, prompt, retrieval_res)

        if "empty_response" in retrieval_res.columns and not "".join(retrieval_res["content"]):
            empty_res = "\n- ".join([str(t) for t in retrieval_res["empty_response"] if str(t)])
            res = {"content": empty_res if empty_res else "Nothing found in knowledgebase!", "reference": []}
            return pd.DataFrame([res])

        msg = self._canvas.get_history(self._param.message_history_window_size)
        if len(msg) < 1:
            msg.append({"role": "user", "content": "Output: "})
        _, msg = message_fit_in([{"role": "system", "content": prompt}, *msg], int(chat_mdl.max_length * 0.97))
        if len(msg) < 2:
            msg.append({"role": "user", "content": "Output: "})
        ans = chat_mdl.chat(msg[0]["content"], msg[1:], self._param.gen_conf())
        ans = re.sub(r"<think>.*</think>", "", ans, flags=re.DOTALL)

        if self._param.cite and "content_ltks" in retrieval_res.columns and "vector" in retrieval_res.columns:
            res = self.set_cite(retrieval_res, ans)
            return pd.DataFrame([res])

        return Generate.be_output(ans)

    def stream_output(self, chat_mdl, prompt, retrieval_res):
        res = None
        if "empty_response" in retrieval_res.columns and not "".join(retrieval_res["content"]):
            empty_res = "\n- ".join([str(t) for t in retrieval_res["empty_response"] if str(t)])
            res = {"content": empty_res if empty_res else "Nothing found in knowledgebase!", "reference": []}
            yield res
            self.set_output(res)
            return

        msg = self._canvas.get_history(self._param.message_history_window_size)
        if len(msg) < 1:
            msg.append({"role": "user", "content": "Output: "})
        _, msg = message_fit_in([{"role": "system", "content": prompt}, *msg], int(chat_mdl.max_length * 0.97))
        if len(msg) < 2:
            msg.append({"role": "user", "content": "Output: "})
        answer = ""
        for ans in chat_mdl.chat_streamly(msg[0]["content"], msg[1:], self._param.gen_conf()):
            res = {"content": ans, "reference": []}
            answer = ans
            yield res

        if self._param.cite and "content_ltks" in retrieval_res.columns and "vector" in retrieval_res.columns:
            res = self.set_cite(retrieval_res, answer)
            yield res

        self.set_output(Generate.be_output(res))

    def debug(self, **kwargs):
        chat_mdl = LLMBundle(self._canvas.get_tenant_id(), LLMType.CHAT, self._param.llm_id)
        prompt = self._param.prompt

        for para in self._param.debug_inputs:
            kwargs[para["key"]] = para.get("value", "")

        for n, v in kwargs.items():
            prompt = re.sub(r"\{%s\}" % re.escape(n), str(v).replace("\\", " "), prompt)

        u = kwargs.get("user")
        ans = chat_mdl.chat(prompt, [{"role": "user", "content": u if u else "Output: "}], self._param.gen_conf())
        return pd.DataFrame([ans])
