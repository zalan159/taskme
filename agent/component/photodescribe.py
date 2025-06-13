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
import base64
from api.db import LLMType
from api.db.services.conversation_service import structure_answer
from api.db.services.llm_service import LLMBundle
from api import settings
from agent.component.base import ComponentBase, ComponentParamBase
from rag.prompts import message_fit_in
from agent.component.generate import GenerateParam, Generate


class PhotoDescribeParam(GenerateParam):
    """
    Define the PhotoDescribe component parameters.
    Inherits from GenerateParam.
    """
    def __init__(self):
        """
        初始化PhotoDescribeParam，设置默认参数值
        """
        super().__init__()
        # 设置默认max_tokens为4096
        self.max_tokens = 4096
        
    def check(self):
        """
        重写父类的check方法，添加对模型名称的检查
        如果选择的模型名称不包含vl关键字则抛出错误
        """
        # 确保max_tokens在有效范围内
        if self.max_tokens is None:
            self.max_tokens = 4096
        if self.max_tokens < 1:
            self.max_tokens = 1
        elif self.max_tokens > 8192:
            self.max_tokens = 8192
            
        # 调用父类的check方法
        super().check()
        
        # 检查模型名称是否包含vl关键字
        if "vl" not in self.llm_id.lower():
            raise ValueError("PhotoDescribe组件需要使用视觉语言模型，当前选择的模型不包含'vl'关键字")


class PhotoDescribe(Generate):
    """
    PhotoDescribe component.
    Inherits from Generate.
    """
    component_name = "PhotoDescribe"
    
    def _run(self, history, **kwargs):
        image_count = 0  # 新增图像计数器
        image_data = None
        
        print("PhotoDescribe组件开始运行")
        
        # 首先检查Begin节点的image_params
        begin_component_instance = self._canvas.get_component("begin")["obj"] # 获取Begin组件实例
        if hasattr(begin_component_instance._param, "image_params") and begin_component_instance._param.image_params:
            print(f"Begin节点image_params数量: {len(begin_component_instance._param.image_params)}")
            # 使用第一个图片参数
            img_param = begin_component_instance._param.image_params[0]
            image_data = img_param.get("value")
            if image_data:
                image_count += 1
                print(f"从Begin节点获取到图片参数: {img_param.get('key')}, 数据长度: {len(image_data)}")
            else:
                print("Begin节点image_params存在但value为空")
        else:
            print("Begin节点没有image_params")
        
        # 如果没有从image_params获取到图片，检查Begin节点的query参数
        if not image_data:
            print("检查Begin节点的query参数")
            for param in begin_component_instance._param.query:
                if param.get("type") == "image" and param.get("value"):
                    image_data = param.get("value")
                    image_count += 1
                    print(f"从Begin节点query参数获取到图片: {param.get('key')}, 数据长度: {len(image_data)}")
                    break
        
        # 如果仍然没有获取到图片，继续原有逻辑
        if not image_data:
            print("从组件连接中查找图片")
            for para in self.get_input_elements()[1:]:
                # 处理begin@参数的特殊情况
                if para["key"].lower().startswith("begin@"):
                    cpn_id, key = para["key"].split("@")
                    # begin_component = self._canvas.get_component(cpn_id)["obj"] # 已在上面获取
                    param_value = ""
                    # 优先从 output_data 获取 (例如 current_date)
                    if hasattr(begin_component_instance._param, "output_data") and key in begin_component_instance._param.output_data:
                        param_value = begin_component_instance._param.output_data[key]
                        print(f"[PhotoDescribe] 从Begin组件的output_data获取到参数 {key} = {param_value}")
                    # 其次从 query 获取 (用户通过begin界面输入的参数)
                    elif hasattr(begin_component_instance._param, "query"):
                        for param_dict in begin_component_instance._param.query:
                            if param_dict.get("key") == key:
                                param_value = param_dict.get("value", "")
                                print(f"[PhotoDescribe] 从Begin组件的query参数获取到 {key} = {str(param_value)[:100]}")
                                break
                    
                    print(f"获取到Begin节点参数 {key} (最终值的前100字符): {str(param_value)[:100]}")
                    
                    # 检查是否为base64图片 (这段逻辑主要用于图片，current_date不需要)
                    if self._is_base64(param_value):
                        print(f"检测到图片输入")
                        image_count += 1  # 增加计数器
                        if image_count == 1:  # 只记录第一个图像
                            image_data = param_value
                    # 尝试处理多行文本中的base64
                    elif param_value and "\n" in param_value:
                        lines = param_value.split("\n")
                        if len(lines) > 1 and self._is_base64(lines[1]):
                            print(f"检测到多行文本中的图片输入")
                            image_count += 1
                            if image_count == 1:
                                image_data = lines[1]
                    continue

                # 处理普通组件输出
                component_id = para["key"]
                cpn = self._canvas.get_component(component_id)["obj"]
                _, out = cpn.output(allow_partial=False)
                value = out["content"].iloc[0] if not out.empty else ""
                print(f"获取到组件 {component_id} 的输出值: {str(value)[:100]}...")
                if self._is_base64(value):
                    print(f"检测到图片输入")
                    image_count += 1  # 增加计数器
                    if image_count == 1:  # 只记录第一个图像
                        image_data = value

        # 新增输入校验逻辑
        if image_count == 0:
            print("未检测到图像输入")
            raise ValueError("未检测到图像输入，请确保已连接图片输入")
        if image_count > 1:
            print(f"检测到{image_count}个图像输入，当前仅支持单张图片处理")
            raise ValueError("检测到多个图像输入，当前仅支持单张图片处理")

        # 原有图像处理逻辑
        if image_data:
            system_prompt = self._param.prompt
            print(f"system_prompt: {system_prompt}")
            image_vars = set()
            
            # 收集所有图片相关的变量名
            for para in self.get_input_elements()[1:]:
                if para["key"].lower().startswith("begin@"):
                    # 处理begin@参数
                    cpn_id, key = para["key"].split("@")
                    # begin_component = self._canvas.get_component(cpn_id)["obj"] # 已在上面获取
                    # 检查是否为图片变量 (这里我们只关心图片变量，current_date不应在此处被标记为image_var)
                    val_for_image_check = ""
                    if hasattr(begin_component_instance._param, "query"):
                        for param_dict in begin_component_instance._param.query:
                            if param_dict.get("key") == key:
                                val_for_image_check = param_dict.get("value", "")
                                break
                    if self._is_base64(val_for_image_check):
                        image_vars.add(f"{{{para['key']}}}")
                else:
                    # 处理普通组件输出
                    component_id = para["key"]
                    cpn = self._canvas.get_component(component_id)["obj"]
                    _, out = cpn.output(allow_partial=False)
                    value = out["content"].iloc[0] if not out.empty else ""
                    if self._is_base64(value):
                        image_vars.add(f"{{{para['key']}}}")

            # 新增：尝试从Begin组件的输出中获取 current_date
            date_from_begin = None
            try:
                # 检查kwargs中是否已经有current_date (虽然日志显示没有)
                if 'current_date' in kwargs:
                    date_from_begin = kwargs['current_date']
                    print(f"[调试日志] 从kwargs直接获取到current_date: {date_from_begin}")
                else:
                    # 尝试从 get_input_elements() 解析
                    # 这需要知道Begin组件的输出是如何被PhotoDescribe的输入参数接收的
                    # 通常，如果Begin的输出是一个包含 'current_date' 键的字典，
                    # 并且这个字典是PhotoDescribe的一个输入参数（例如，名为 "begin_data"）
                    # 那么它会出现在kwargs['begin_data']['current_date']
                    # 或者，如果Begin组件的每个输出字段都作为单独的输入：
                    # kwargs['current_date'] （但日志否定了这一点）

                    # 暂时我们假设，如果Begin组件连接了，它的current_date应该在kwargs中
                    # 如果不在，说明连接或数据传递有问题。
                    # 我们也可以尝试直接从Begin组件实例获取其最新输出，但这耦合度较高。

                    # 考虑到Begin组件的输出是 pd.DataFrame([{"content": prolog, "current_date": date}])
                    # PhotoDescribe组件如何接收这个DataFrame?
                    # 它可能是作为kwargs中的一个特定条目，例如 kwargs['input_df']
                    # 或者 PhotoDescribe的父类Generate已经处理了这个输入，并将其内容放到了某个地方

                    # 在Generate组件的通用逻辑中，输入通常是通过 kwargs 传递的。
                    # 如果kwargs中没有current_date，那么Begin组件的输出没有正确地作为命名参数传递给PhotoDescribe的_run方法。

                    # 让我们假设kwargs应该包含Begin组件输出DataFrame的解包内容。
                    # 如果Begin组件的输出是{'content': '...', 'current_date': '...'}
                    # 那么调用PhotoDescribe._run时，应该像 PhotoDescribe._run(..., content='...', current_date='...')
                    # 但日志显示kwargs只有{'stream': True}

                    print(f"[调试日志] kwargs中未找到current_date。当前kwargs: {kwargs}")
                    # 如果Begin组件是作为非kwargs的第一个参数传递的，那需要修改_run的签名
                    # 但通常组件的输入是通过kwargs或者特定的父类方法获取的。

                    # 再次检查`Generate`类是如何处理输入的。
                    # Generate类的_run方法签名是 _run(self, history, **kwargs)
                    # 它会调用 self._param.prompt.format(**kwargs)
                    # 这意味着所有用于替换的变量都必须在kwargs中。

                    # 所以，核心问题是：Begin组件输出的 current_date 如何进入 PhotoDescribe 的 kwargs？
                    # 这通常由工作流引擎根据组件连接自动完成。
                    # 如果没有自动完成，可能需要在PhotoDescribe中显式拉取，或者修改Begin的输出方式/工作流配置。

                    # 为了更直接地解决，如果Begin组件总是作为PhotoDescribe的直接上游，
                    # 我们可以尝试在PhotoDescribe中直接引用Begin组件并获取其输出。
                    begin_component_obj = self._canvas.get_component_by_name("Begin") # 假设有此方法或类似方法
                    if begin_component_obj:
                        # 假设Begin组件有一个output()方法或者一个存储最后输出的属性
                        # last_begin_output = begin_component_obj.get_last_output() # 这需要Begin组件实现
                        # if last_begin_output and "current_date" in last_begin_output:
                        # date_from_begin = last_begin_output["current_date"]
                        # print(f"[调试日志] 通过直接访问Begin组件获取到 current_date: {date_from_begin}")

                        # 一个更实际的做法是，Begin组件的输出应该作为数据输入流传递。
                        # get_input_elements() 应该包含Begin的输出。
                        # input_elements = self.get_input_elements()
                        # for element in input_elements:
                            # if element is from Begin and contains current_date
                            #   date_from_begin = element_data['current_date']
                        # 这个逻辑太复杂，且依赖具体的数据结构。

                        # 最终，如果kwargs里没有，替换就不会发生。
                        # 我们应该专注于为什么Begin的输出没进入kwargs。
                        pass # 保持原样，因为修改这里需要更多框架细节


            except Exception as e:
                print(f"[调试日志] 尝试获取current_date时发生错误: {e}")

            # 进行变量替换时跳过图片变量
            # 将date_from_begin添加到kwargs，如果获取到了的话
            current_processing_kwargs = {**kwargs} 

            # 新增：将通过 begin@key 方式获取到的值，加入到替换参数中
            # 这些值是从 get_input_elements() 间接获得的，需要手动加入 current_processing_kwargs
            # 以确保它们能被用于 .format() 或 re.sub()

            # 从Begin组件的output_data中提取所有值并添加到替换字典
            if hasattr(begin_component_instance._param, "output_data"):
                for k, v in begin_component_instance._param.output_data.items():
                    # 构建 PhotoDescribe 中 prompt 使用的占位符，如 {begin@current_date}
                    placeholder_key_in_prompt = f"begin@{k}" 
                    current_processing_kwargs[placeholder_key_in_prompt] = v
                    print(f"[PhotoDescribe] 将 {placeholder_key_in_prompt}={v} 添加到替换参数 current_processing_kwargs")

            # 同时，也处理Begin组件的query参数 (如 {begin@test} )
            if hasattr(begin_component_instance._param, "query"):
                for param_dict in begin_component_instance._param.query:
                    k_query = param_dict.get("key")
                    v_query = param_dict.get("value")
                    if k_query and v_query is not None: #确保有值
                        placeholder_key_in_prompt = f"begin@{k_query}"
                        # 只有当这个占位符还没有被output_data中的同名key覆盖时才添加
                        if placeholder_key_in_prompt not in current_processing_kwargs or not current_processing_kwargs[placeholder_key_in_prompt]:
                            current_processing_kwargs[placeholder_key_in_prompt] = v_query
                            print(f"[PhotoDescribe] 将 {placeholder_key_in_prompt}={str(v_query)[:50]}... 添加到替换参数 current_processing_kwargs (来自query)")
            
            # 对于直接连接的其他组件的输出 (例如 {对话_0})
            # 这些通常是作为 kwargs 的一部分传入的，或者是通过 Generate 基类的机制处理
            # 如果它们不在kwargs中，这里的 current_processing_kwargs 也不会包含它们，除非Generate基类有特殊处理
            # 我们从日志看到 kwargs 只包含 stream，所以其他组件的输出 {对话_0} 如果需要替换，
            # 也需要类似 begin@ 的机制或者被正确地放入kwargs

            print(f"[调试日志] 用于替换的参数(current_processing_kwargs): {current_processing_kwargs}")
            print(f"[调试日志] 替换前原始system_prompt: {system_prompt}")
            
            pattern = re.compile(r"\\{(" + "|".join(map(re.escape, [v[1:-1] for v in image_vars])) + r")\\}") if image_vars else None
            
            # print(f"[调试日志] 传入的kwargs: {kwargs}") # 这行已在之前添加

            # 注意：这里的替换逻辑是遍历 current_processing_kwargs
            # 而 system_prompt 中的占位符是类似 {begin@current_date} 或 {对话_0}
            # 所以 current_processing_kwargs 中的键需要和 prompt 中的占位符匹配（去掉花括号）
            for n_placeholder, v_value in current_processing_kwargs.items():
                # n_placeholder 已经是占位符的名称了，例如 "begin@current_date"
                var_pattern_in_prompt = f"{{{n_placeholder}}}" # 构建形如 {begin@current_date} 的正则表达式
                print(f"[调试日志] 尝试替换: 占位符='{var_pattern_in_prompt}', 值='{str(v_value)[:100]}...'")
                # 确保这个占位符不是图片变量的占位符
                is_image_var_placeholder = False
                for img_var_placeholder in image_vars: # image_vars 包含的是形如 {begin@some_image_param}
                    if img_var_placeholder == var_pattern_in_prompt:
                        is_image_var_placeholder = True
                        break
                
                if not is_image_var_placeholder:
                    original_prompt_before_sub = system_prompt
                    system_prompt = re.sub(re.escape(var_pattern_in_prompt), str(v_value).replace("\\", " "), system_prompt)
                    if original_prompt_before_sub != system_prompt:
                        print(f"[调试日志] 对'{var_pattern_in_prompt}'的替换已发生。替换后system_prompt: {system_prompt}")
                    else:
                        print(f"[调试日志] 对'{var_pattern_in_prompt}'的替换未发生 (占位符可能未在prompt中找到)。")
                else:
                    print(f"[调试日志] 跳过图片变量占位符 '{var_pattern_in_prompt}' 的替换。")
            
            print(f"[调试日志] 所有替换完成后最终的system_prompt: {system_prompt}") # 打印最终的prompt
            
            # 获取max_tokens参数值，并确保正确传递
            max_tokens = self._param.max_tokens
            print(f"使用max_tokens值: {max_tokens}")
            
            # 确保max_tokens值有效
            if max_tokens is None or max_tokens < 1:
                max_tokens = 4096
                print(f"max_tokens无效，使用默认值: {max_tokens}")
            elif max_tokens > 8192:
                max_tokens = 8192
                print(f"max_tokens超出范围，调整为: {max_tokens}")
                
            # 使用cv_with_prompt方法处理图像
            cv_mdl = LLMBundle(self._canvas.get_tenant_id(), LLMType.IMAGE2TEXT, self._param.llm_id)
            result = cv_mdl.cv_with_prompt(image_data, system_prompt, max_tokens)
            
            return pd.DataFrame([{
                "content": result,
                "reference": []
            }])

        # 调用父类原有逻辑
        # return super()._run(history, **kwargs)

    def _is_base64(self, s):
        """优化后的base64检测逻辑"""
        if not s:
            return False
            
        try:
            # 打印前100个字符，帮助调试
            print(f"检查是否为base64: {str(s)[:100]}...")
            
            # 如果是字符串类型，检查是否为base64格式
            if isinstance(s, str):
                # 匹配data URI格式
                if re.match(r"^data:image/\w+;base64,", s):
                    print("检测到data:image格式")
                    data_part = s.split(",", 1)[1]
                    return base64.b64decode(data_part, validate=True) and len(data_part) % 4 == 0
                
                # 检查是否包含换行符，如果有，可能是多行base64
                if "\n" in s:
                    # 尝试获取第二行作为base64数据
                    try:
                        print("检测到多行格式，尝试获取第二行")
                        data_part = s.split("\n")[1]
                        return base64.b64decode(data_part, validate=True) and len(data_part) % 4 == 0
                    except:
                        pass
                
                # 尝试直接解码
                try:
                    print("尝试直接解码")
                    base64.b64decode(s, validate=True)
                    return len(s) % 4 == 0
                except:
                    pass
                    
            return False
        except Exception as e:
            print(f"Base64检测异常: {str(e)}")
            return False