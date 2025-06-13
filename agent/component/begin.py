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
import datetime
from functools import partial
import pandas as pd
from agent.component.base import ComponentBase, ComponentParamBase


class BeginParam(ComponentParamBase):

    """
    Define the Begin component parameters.
    """
    def __init__(self):
        super().__init__()
        self.prologue = "Hi! I'm your smart assistant. What can I do for you?"
        self.query = []
        # 添加图片参数列表，用于存储用户输入的图片
        self.image_params = []
        # 新增：用于存储Begin组件想要输出给其他组件通过特定方式查询的数据
        self.output_data = {}

    def check(self):
        # 检查query中是否有图片类型的参数，如果有，添加到image_params中
        for q in self.query:
            if q.get("type") == "image" and q.get("value"):
                # 确保图片参数不重复添加
                if not any(img["key"] == q["key"] for img in self.image_params):
                    self.image_params.append(q)
        return True


class Begin(ComponentBase):
    component_name = "Begin"

    def _run(self, history, **kwargs):
        now = datetime.datetime.now()
        # 生成格式如 "2025年5月29日" 的日期字符串
        formatted_date = f"{now.year}年{now.month}月{now.day}日"
        
        # 将日期存储到 param 的 output_data 中，以便其他组件通过类似 begin@key 的方式读取
        self._param.output_data["current_date"] = formatted_date
        print(f"[Begin组件日志] 已将 current_date: {formatted_date} 存储到 self._param.output_data")

        output_payload = {
            "content": self._param.prologue,
            # "current_date": formatted_date # 从payload中移除，因为它现在通过param.output_data提供
        }

        if kwargs.get("stream"):
            # stream_output 方法也需要能提供日期，如果流式输出也需要这个日期的话
            # 但目前看，PhotoDescribe是非流式组件，主要关注非流式路径
            return partial(self.stream_output)
        
        return pd.DataFrame([output_payload])

    def stream_output(self):
        now = datetime.datetime.now()
        formatted_date = f"{now.year}年{now.month}月{now.day}日"
        # 如果流式输出也需要通过param共享，也应在此处设置
        # self._param.output_data["current_date"] = formatted_date 
        
        res = {
            "content": self._param.prologue,
            # "current_date": formatted_date # 从流式输出的直接结果中移除
        }
        yield res
        self.set_output(self.be_output(res))



