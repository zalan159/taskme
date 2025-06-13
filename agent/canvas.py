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
import logging
import json
from copy import deepcopy
from functools import partial

import pandas as pd

from agent.component import component_class
from agent.component.base import ComponentBase
from api.db.services.user_service import TenantService


class Canvas:
    """
    dsl = {
        "components": {
            "begin": {
                "obj":{
                    "component_name": "Begin",
                    "params": {},
                },
                "downstream": ["answer_0"],
                "upstream": [],
            },
            "answer_0": {
                "obj": {
                    "component_name": "Answer",
                    "params": {}
                },
                "downstream": ["retrieval_0"],
                "upstream": ["begin", "generate_0"],
            },
            "retrieval_0": {
                "obj": {
                    "component_name": "Retrieval",
                    "params": {}
                },
                "downstream": ["generate_0"],
                "upstream": ["answer_0"],
            },
            "generate_0": {
                "obj": {
                    "component_name": "Generate",
                    "params": {}
                },
                "downstream": ["answer_0"],
                "upstream": ["retrieval_0"],
            }
        },
        "history": [],
        "messages": [],
        "reference": [],
        "path": [["begin"]],
        "answer": []
    }
    """

    def __init__(self, dsl: str, tenant_id=None):
        self.path = []
        self.history = []
        self.messages = []
        self.answer = []
        self.components = {}
        self._last_error = None  # 存储最后一个错误消息
        self.dsl = json.loads(dsl) if dsl else {
            "components": {
                "begin": {
                    "obj": {
                        "component_name": "Begin",
                        "params": {
                            "prologue": "Hi there!"
                        }
                    },
                    "downstream": [],
                    "upstream": [],
                    "parent_id": ""
                }
            },
            "history": [],
            "messages": [],
            "reference": [],
            "path": [],
            "answer": []
        }
        self._tenant_id = tenant_id
        self._embed_id = ""
        self.load()

    def load(self):
        self.components = self.dsl["components"]
        cpn_nms = set([])
        for k, cpn in self.components.items():
            cpn_nms.add(cpn["obj"]["component_name"])

        assert "Begin" in cpn_nms, "There have to be an 'Begin' component."
        assert "Answer" in cpn_nms, "There have to be an 'Answer' component."

        for k, cpn in self.components.items():
            cpn_nms.add(cpn["obj"]["component_name"])
            param = component_class(cpn["obj"]["component_name"] + "Param")()
            param.update(cpn["obj"]["params"])
            
            # 特殊处理Begin组件的图片参数
            if cpn["obj"]["component_name"] == "Begin":
                # 检查query中是否有图片类型的参数
                for q in param.query:
                    if q.get("type") == "image" and q.get("value"):
                        # 确保image_params存在
                        if not hasattr(param, "image_params"):
                            param.image_params = []
                        # 确保图片参数不重复添加
                        if not any(img["key"] == q["key"] for img in param.image_params):
                            param.image_params.append(q)
            
            param.check()
            if cpn["obj"]["component_name"] == "MCP":
                credential = TenantService.get_mcp_credential(self._tenant_id)
                cpn["obj"] = component_class(cpn["obj"]["component_name"])(
                    self, k, param,
                    api_key=credential["api_key"],
                    model_name=credential["model_name"],
                    base_url=credential["base_url"]
                )
            else:
                cpn["obj"] = component_class(cpn["obj"]["component_name"])(self, k, param)

            if cpn["obj"].component_name == "Categorize":
                for _, desc in param.category_description.items():
                    if desc["to"] not in cpn["downstream"]:
                        cpn["downstream"].append(desc["to"])

        self.path = self.dsl["path"]
        self.history = self.dsl["history"]
        self.messages = self.dsl["messages"]
        self.answer = self.dsl["answer"]
        self.reference = self.dsl["reference"]
        self._embed_id = self.dsl.get("embed_id", "")

    def __str__(self):
        self.dsl["path"] = self.path
        self.dsl["history"] = self.history
        self.dsl["messages"] = self.messages
        self.dsl["answer"] = self.answer
        self.dsl["reference"] = self.reference
        self.dsl["embed_id"] = self._embed_id
        dsl = {
            "components": {}
        }
        for k in self.dsl.keys():
            if k in ["components"]:
                continue
            dsl[k] = deepcopy(self.dsl[k])

        for k, cpn in self.components.items():
            if k not in dsl["components"]:
                dsl["components"][k] = {}
            for c in cpn.keys():
                if c == "obj":
                    obj_dict = json.loads(str(cpn["obj"]))
                    # 确保图片参数被正确保存
                    if k == "begin" and hasattr(cpn["obj"]._param, "image_params") and cpn["obj"]._param.image_params:
                        # 确保query中包含所有图片参数
                        for img_param in cpn["obj"]._param.image_params:
                            # 检查query中是否已存在该图片参数
                            param_exists = False
                            for q in obj_dict["params"]["query"]:
                                if q["key"] == img_param["key"]:
                                    q["value"] = img_param["value"]
                                    q["type"] = "image"
                                    param_exists = True
                                    break
                            
                            # 如果不存在，添加到query中
                            if not param_exists:
                                obj_dict["params"]["query"].append({
                                    "key": img_param["key"],
                                    "value": img_param["value"],
                                    "type": "image"
                                })
                    
                    dsl["components"][k][c] = obj_dict
                    continue
                dsl["components"][k][c] = deepcopy(cpn[c])
        return json.dumps(dsl, ensure_ascii=False)

    def reset(self):
        self.path = []
        self.history = []
        self.messages = []
        self.answer = []
        self.reference = []
        self._last_error = None  # 重置错误信息
        for k, cpn in self.components.items():
            self.components[k]["obj"].reset()
        self._embed_id = ""

    def get_component_name(self, cid):
        for n in self.dsl["graph"]["nodes"]:
            if cid == n["id"]:
                return n["data"]["name"]
        return ""

    def run(self, **kwargs):
        if self.answer:
            cpn_id = self.answer[0]
            self.answer.pop(0)
            try:
                # 检查是否有存储的错误信息需要返回
                if self._last_error and self.components[cpn_id]["obj"].component_name == "Answer":
                    # 使用存储的错误信息替代正常输出
                    error_message = self._last_error
                    self._last_error = None  # 清除错误信息，避免重复显示
                    ans = ComponentBase.be_output(error_message, is_error=False)
                else:
                    # 正常执行组件
                    ans = self.components[cpn_id]["obj"].run(self.history, **kwargs)
            except Exception as e:
                error_message = str(e)
                # 检查是否是PhotoDescribe组件的特定输入校验错误
                if "未检测到图像输入" in error_message or "检测到多个图像输入" in error_message:
                    # 对于PhotoDescribe的校验错误，直接返回错误信息作为正常输出
                    ans = ComponentBase.be_output(error_message, is_error=False)
                else:
                    # 其他错误仍然作为错误处理
                    ans = ComponentBase.be_output(error_message, is_error=True)
            self.path[-1].append(cpn_id)
            if kwargs.get("stream"):
                if callable(ans):
                    for an in ans():
                        yield an
                else:
                    yield ans
            else:
                yield ans
            return

        if not self.path:
            self.components["begin"]["obj"].run(self.history, **kwargs)
            self.path.append(["begin"])

        self.path.append([])

        ran = -1
        waiting = []
        without_dependent_checking = []

        def prepare2run(cpns):
            nonlocal ran, ans
            for c in cpns:
                if self.path[-1] and c == self.path[-1][-1]:
                    continue
                cpn = self.components[c]["obj"]
                if cpn.component_name == "Answer":
                    self.answer.append(c)
                else:
                    logging.debug(f"Canvas.prepare2run: {c}")
                    if c not in without_dependent_checking:
                        cpids = cpn.get_dependent_components()
                        if any([cc not in self.path[-1] for cc in cpids]):
                            if c not in waiting:
                                waiting.append(c)
                            continue
                    yield "*'{}'* is running...🕞".format(self.get_component_name(c))

                    if cpn.component_name.lower() == "iteration":
                        st_cpn = cpn.get_start()
                        assert st_cpn, "Start component not found for Iteration."
                        if not st_cpn["obj"].end():
                            cpn = st_cpn["obj"]
                            c = cpn._id

                    try:
                        ans = cpn.run(self.history, **kwargs)
                    except Exception as e:
                        logging.exception(f"Canvas.run got exception: {e}")
                        self.path[-1].append(c)
                        ran += 1
                        
                        error_message = str(e)
                        # 检查是否是PhotoDescribe组件的特定输入校验错误
                        if "未检测到图像输入" in error_message or "检测到多个图像输入" in error_message:
                            # 对于PhotoDescribe的校验错误，记录后继续
                            logging.info(f"组件 {cpn.component_name} 输入校验错误: {error_message}")
                            # 将错误添加到Answer组件，以确保它能被返回给用户
                            answer_components = [cid for cid, comp in self.components.items() 
                                              if comp["obj"].component_name == "Answer"]
                            if answer_components:
                                self.answer.append(answer_components[0])
                                # 设置错误信息，以便后续返回
                                self._last_error = error_message
                        
                        # 继续抛出异常，让上层处理
                        raise e
                    self.path[-1].append(c)

            ran += 1

        downstream = self.components[self.path[-2][-1]]["downstream"]
        if not downstream and self.components[self.path[-2][-1]].get("parent_id"):
            cid = self.path[-2][-1]
            pid = self.components[cid]["parent_id"]
            o, _ = self.components[cid]["obj"].output(allow_partial=False)
            oo, _ = self.components[pid]["obj"].output(allow_partial=False)
            self.components[pid]["obj"].set(pd.concat([oo, o], ignore_index=True))
            downstream = [pid]

        for m in prepare2run(downstream):
            yield {"content": m, "running_status": True}

        while 0 <= ran < len(self.path[-1]):
            logging.debug(f"Canvas.run: {ran} {self.path}")
            cpn_id = self.path[-1][ran]
            cpn = self.get_component(cpn_id)
            if not any([cpn["downstream"], cpn.get("parent_id"), waiting]):
                break

            loop = self._find_loop()
            if loop:
                raise OverflowError(f"Too much loops: {loop}")

            if cpn["obj"].component_name.lower() in ["switch", "categorize", "relevant"]:
                switch_out = cpn["obj"].output()[1].iloc[0, 0]
                assert switch_out in self.components, \
                    "{}'s output: {} not valid.".format(cpn_id, switch_out)
                for m in prepare2run([switch_out]):
                    yield {"content": m, "running_status": True}
                continue

            downstream = cpn["downstream"]
            if not downstream and cpn.get("parent_id"):
                pid = cpn["parent_id"]
                _, o = cpn["obj"].output(allow_partial=False)
                _, oo = self.components[pid]["obj"].output(allow_partial=False)
                self.components[pid]["obj"].set_output(pd.concat([oo.dropna(axis=1), o.dropna(axis=1)], ignore_index=True))
                downstream = [pid]

            for m in prepare2run(downstream):
                yield {"content": m, "running_status": True}

            if ran >= len(self.path[-1]) and waiting:
                without_dependent_checking = waiting
                waiting = []
                for m in prepare2run(without_dependent_checking):
                    yield {"content": m, "running_status": True}
                without_dependent_checking = []
                ran -= 1

        if self.answer:
            cpn_id = self.answer[0]
            self.answer.pop(0)
            ans = self.components[cpn_id]["obj"].run(self.history, **kwargs)
            self.path[-1].append(cpn_id)
            if kwargs.get("stream"):
                if callable(ans):
                    for an in ans():
                        yield an
                else:
                    yield ans
            else:
                yield ans

        else:
            raise Exception("The dialog flow has no way to interact with you. Please add an 'Interact' component to the end of the flow.")

    def get_component(self, cpn_id):
        return self.components[cpn_id]

    def get_tenant_id(self):
        return self._tenant_id

    def get_history(self, window_size):
        convs = []
        for role, obj in self.history[window_size * -1:]:
            if isinstance(obj, list) and obj and all([isinstance(o, dict) for o in obj]):
                convs.append({"role": role, "content": '\n'.join([str(s.get("content", "")) for s in obj])})
            else:
                convs.append({"role": role, "content": str(obj)})
        return convs

    def add_user_input(self, question):
        self.history.append(("user", question))

    def add_image_input(self, image_data, image_name="image"):
        """
        添加图片输入到画布
        
        Args:
            image_data: base64编码的图片数据
            image_name: 图片的名称标识符
        """
        print(f"添加图片输入: {image_name}, 数据长度: {len(image_data) if image_data else 0}")
        
        # 确保Begin组件存在
        if "begin" not in self.components:
            print("错误: Begin组件不存在")
            return
            
        # 确保Begin组件的_param存在
        if not hasattr(self.components["begin"]["obj"], "_param"):
            print("错误: Begin组件的_param不存在")
            return
            
        # 确保_param.query存在
        if not hasattr(self.components["begin"]["obj"]._param, "query"):
            self.components["begin"]["obj"]._param.query = []
            
        # 确保_param.image_params存在
        if not hasattr(self.components["begin"]["obj"]._param, "image_params"):
            self.components["begin"]["obj"]._param.image_params = []
        
        # 将图片数据添加到Begin组件的参数中
        found = False
        for q in self.components["begin"]["obj"]._param.query:
            if q["key"] == image_name:
                q["value"] = image_data
                q["type"] = "image"
                found = True
                print(f"更新现有参数: {image_name}")
                break
            
        # 如果不存在相应的参数，则添加一个新的
        if not found:
            new_param = {
                "key": image_name,
                "value": image_data,
                "type": "image"
            }
            self.components["begin"]["obj"]._param.query.append(new_param)
            print(f"添加新参数: {image_name}")
            
        # 更新image_params
        # 检查image_params中是否已存在该参数
        found = False
        for img in self.components["begin"]["obj"]._param.image_params:
            if img["key"] == image_name:
                img["value"] = image_data
                found = True
                print(f"更新image_params: {image_name}")
                break
                
        # 如果不存在，添加到image_params
        if not found:
            self.components["begin"]["obj"]._param.image_params.append({
                "key": image_name,
                "value": image_data,
                "type": "image"
            })
            print(f"添加到image_params: {image_name}")
            
        print(f"Begin组件现有query参数数量: {len(self.components['begin']['obj']._param.query)}")
        print(f"Begin组件现有image_params数量: {len(self.components['begin']['obj']._param.image_params)}")

    def set_embedding_model(self, embed_id):
        self._embed_id = embed_id

    def get_embedding_model(self):
        return self._embed_id

    def _find_loop(self, max_loops=6):
        path = self.path[-1][::-1]
        if len(path) < 2:
            return False

        for i in range(len(path)):
            if path[i].lower().find("answer") == 0 or path[i].lower().find("iterationitem") == 0:
                path = path[:i]
                break

        if len(path) < 2:
            return False

        for loc in range(2, len(path) // 2):
            pat = ",".join(path[0:loc])
            path_str = ",".join(path)
            if len(pat) >= len(path_str):
                return False
            loop = max_loops
            while path_str.find(pat) == 0 and loop >= 0:
                loop -= 1
                if len(pat)+1 >= len(path_str):
                    return False
                path_str = path_str[len(pat)+1:]
            if loop < 0:
                pat = " => ".join([p.split(":")[0] for p in path[0:loc]])
                return pat + " => " + pat

        return False

    def get_prologue(self):
        return self.components["begin"]["obj"]._param.prologue

    def set_global_param(self, **kwargs):
        for k, v in kwargs.items():
            for q in self.components["begin"]["obj"]._param.query:
                if k != q["key"]:
                    continue
                q["value"] = v

    def get_preset_param(self):
        return self.components["begin"]["obj"]._param.query

    def get_component_input_elements(self, cpnnm):
        return self.components[cpnnm]["obj"].get_input_elements()