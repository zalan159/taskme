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
import json
import time
import traceback
from uuid import uuid4
from agent.canvas import Canvas
from api.db.db_models import DB, CanvasTemplate, UserCanvas, API4Conversation, CanvasInfo, CanvasTenant
from api.db.services.api_service import API4ConversationService
from api.db.services.common_service import CommonService
from api.db.services.conversation_service import structure_answer
from api.db.services.user_service import UserTenantService
from api.utils import get_uuid


class CanvasTemplateService(CommonService):
    model = CanvasTemplate

class CanvasInfoService(CommonService):
    model = CanvasInfo

class CanvasTenantService(CommonService):
    model = CanvasTenant

class UserCanvasService(CommonService):
    model = UserCanvas

    @classmethod
    @DB.connection_context()
    def get_list(cls, tenant_id,
                 page_number, items_per_page, orderby, desc, id, title):
        # 1. 获取用户自己的canvas
        agents = cls.model.select()
        if id:
            agents = agents.where(cls.model.id == id)
        if title:
            agents = agents.where(cls.model.title == title)
        agents = agents.where(cls.model.user_id == tenant_id)
        
        # 2. 获取团队canvas
        team_canvases = []
        tenants = UserTenantService.get_tenants_by_user_id(tenant_id)
        if tenants:
            for tenant in tenants:
                canvas_tenants = CanvasTenant.select().where(CanvasTenant.tenant_id == tenant['tenant_id'])
                for c in canvas_tenants:
                    canvas = cls.get_or_none(id=c.canvas_id)
                    if canvas and canvas.id not in [a.id for a in agents]:  # 排除用户自己的canvas
                        team_canvases.append(canvas)
        
        # 3. 获取公共canvas
        public_canvases = []
        public_canvas_infos = CanvasInfo.select().where(CanvasInfo.canvas_permissions == 'public')
        for info in public_canvas_infos:
            canvas = cls.get_or_none(id=info.canvas_id)
            if canvas and canvas.id not in [a.id for a in agents]:  # 排除用户自己的canvas
                public_canvases.append(canvas)
        
        # 4. 合并所有canvas
        all_canvases = list(agents)
        all_canvases.extend(team_canvases)
        all_canvases.extend(public_canvases)
        
        # 5. 排序
        if desc:
            all_canvases.sort(key=lambda x: getattr(x, orderby), reverse=True)
        else:
            all_canvases.sort(key=lambda x: getattr(x, orderby))
            
        # 6. 分页
        start_idx = (page_number - 1) * items_per_page
        end_idx = start_idx + items_per_page
        paginated_canvases = all_canvases[start_idx:end_idx]
        
        return [c.to_dict() for c in paginated_canvases]


def completion(tenant_id, agent_id, question, session_id=None, stream=True, **kwargs):
    e, cvs = UserCanvasService.get_by_id(agent_id)
    assert e, "Agent not found."
    # assert cvs.user_id == tenant_id, "You do not own the agent."
    if not isinstance(cvs.dsl,str):
        cvs.dsl = json.dumps(cvs.dsl, ensure_ascii=False)
    canvas = Canvas(cvs.dsl, tenant_id)
    canvas.reset()
    message_id = str(uuid4())
    if not session_id:
        query = canvas.get_preset_param()
        if query:
            for ele in query:
                if not ele["optional"]:
                    if not kwargs.get(ele["key"]):
                        assert False, f"`{ele['key']}` is required"
                    ele["value"] = kwargs[ele["key"]]
                if ele["optional"]:
                    if kwargs.get(ele["key"]):
                        ele["value"] = kwargs[ele['key']]
                    else:
                        if "value" in ele:
                            ele.pop("value")
        cvs.dsl = json.loads(str(canvas))
        session_id=get_uuid()
        conv = {
            "id": session_id,
            "dialog_id": cvs.id,
            "user_id": kwargs.get("user_id", "") if isinstance(kwargs, dict) else "",
            "message": [{"role": "assistant", "content": canvas.get_prologue(), "created_at": time.time()}],
            "source": "agent",
            "dsl": cvs.dsl
        }
        API4ConversationService.save(**conv)
        if query:
            yield "data:" + json.dumps({"code": 0,
                                        "message": "",
                                        "data": {
                                            "session_id": session_id,
                                            "answer": canvas.get_prologue(),
                                            "reference": [],
                                            "param": canvas.get_preset_param()
                                        }
                                        },
                                       ensure_ascii=False) + "\n\n"
            yield "data:" + json.dumps({"code": 0, "message": "", "data": True}, ensure_ascii=False) + "\n\n"
            return
        else:
            conv = API4Conversation(**conv)
    else:
        e, conv = API4ConversationService.get_by_id(session_id)
        assert e, "Session not found!"
        canvas = Canvas(json.dumps(conv.dsl), tenant_id)
        canvas.reset()
        
        # 检查是否有预设参数
        query = canvas.get_preset_param()
        print("当前有预设参数：", query)
        
        # 添加用户消息和输入
        canvas.messages.append({"role": "user", "content": question, "id": message_id})
        canvas.add_user_input(question)

        # 标记是否有图片上传
        has_images = kwargs and "images" in kwargs and isinstance(kwargs["images"], list) and len(kwargs["images"]) > 0
        
        # 检查当前是否是第一条用户消息
        user_messages_count = sum(1 for msg in conv.message if msg.get("role") == "user")
        is_first_user_interaction = user_messages_count == 0 # 如果会话中还没有用户消息，那么当前就是第一次用户交互

        # 如果是"新对话"且是用户的首次交互，则尝试更新会话摘要
        if conv.summary == "新对话" and is_first_user_interaction:
            print(f"会话 '{session_id}' 是新对话且为首次用户交互，尝试更新摘要。")
            new_summary_content = ""
            if question and question.strip():
                new_summary_content = question.strip()
                print(f"使用用户输入文本作为摘要基础: '{new_summary_content[:50]}'")
            elif has_images:
                try:
                    first_image_name = kwargs["images"][0].get("name", "图片消息")
                    new_summary_content = first_image_name
                    print(f"使用第一张图片名作为摘要基础: '{new_summary_content[:50]}'")
                except Exception as img_e:
                    print(f"提取图片名称时出错: {img_e}")
                    new_summary_content = "图片消息"
            
            if new_summary_content:
                conv.summary = new_summary_content[:50] # 更新会话对象的summary字段
                print(f"会话 '{session_id}' 的摘要已更新为: '{conv.summary}'")
            else:
                print(f"未能从用户输入或图片中提取有效内容作为新摘要，保持原有摘要 '{conv.summary}'")

        # 检查当前是否是第一条用户消息 (这里是为了后续的旧数据清理逻辑，与上面的摘要更新逻辑中的 is_first_user_interaction 定义略有不同)
        user_messages_for_cleanup = [msg for msg in conv.message if msg.get("role") == "user"]
        is_first_message_for_cleanup = len(user_messages_for_cleanup) == 0
        
        # 为所有消息处理（不管是文字还是图片）：在非第一条消息时清除旧数据
        if not is_first_message_for_cleanup:
            # 清除Begin组件中的旧数据
            print("清除Begin组件中的旧数据（包括图片和其他参数）")
            begin_param = canvas.components["begin"]["obj"]._param
            
            # 清除query中的图片参数
            if hasattr(begin_param, "query"):
                # 过滤出非图片参数
                begin_param.query = [q for q in begin_param.query if q.get("type") != "image"]
                print(f"清除后query参数数量: {len(begin_param.query)}")
            
            # 清除image_params
            if hasattr(begin_param, "image_params"):
                begin_param.image_params = []
                print(f"清除图片参数列表")
        else:
            print("首次用户消息，保留原有行为")
        
        if has_images:
            print(f"处理新上传的 {len(kwargs['images'])} 张图片")
            
            # 关联图片到当前消息
            for msg in canvas.messages:
                if msg.get("id") == message_id:
                    msg["images"] = kwargs["images"]
                    print(f"为消息 {message_id} 关联 {len(kwargs['images'])} 张图片")
                    break
            
            # 处理每张图片
            for idx, img in enumerate(kwargs["images"]):
                img_data = img.get("data", "")
                img_name = img.get("name", f"image{idx+1}")
                if img_data:
                    # 每张图片使用唯一标识符
                    unique_img_name = f"new_image_{message_id}_{idx}_{img_name}"
                    print(f"添加新图片: {unique_img_name}, 数据长度: {len(img_data)}")
                    canvas.add_image_input(img_data, unique_img_name)
                else:
                    print(f"图片 {img_name} 数据为空")

        # 更新会话消息
        if not conv.message:
            conv.message = []
        
        current_message = {
            "role": "user",
            "content": question,
            "id": message_id
        }
        
        if has_images:
            current_message["images"] = kwargs["images"]
            print(f"将 {len(kwargs['images'])} 张图片添加到会话消息 {message_id}")
        
        conv.message.append(current_message)
        
        # 更新引用相关代码...
        if not conv.reference:
            conv.reference = []
        conv.reference.append({"chunks": [], "doc_aggs": []})
        
        
        # 始终使用Begin组件的下游组件
        downstream = canvas.components["begin"]["downstream"]
        print(f"使用Begin组件的下游组件: {downstream}")
        canvas.path = [["begin"], downstream]
        
        # 记录是否有图片（仅用于日志记录）
        if has_images:
            print(f"消息包含 {len(kwargs['images'])} 张图片")
        else:
            print("消息不包含图片")

    final_ans = {"reference": [], "content": ""}
    if stream:
        try:
            for ans in canvas.run(stream=stream):
                if ans.get("running_status"):
                    yield "data:" + json.dumps({"code": 0, "message": "",
                                                "data": {"answer": ans["content"],
                                                         "running_status": True}},
                                               ensure_ascii=False) + "\n\n"
                    continue
                for k in ans.keys():
                    final_ans[k] = ans[k]
                ans = {"answer": ans["content"], "reference": ans.get("reference", [])}
                ans = structure_answer(conv, ans, message_id, session_id)
                yield "data:" + json.dumps({"code": 0, "message": "", "data": ans},
                                           ensure_ascii=False) + "\n\n"

            canvas.messages.append({"role": "assistant", "content": final_ans["content"], "created_at": time.time(), "id": message_id})
            canvas.history.append(("assistant", final_ans["content"]))
            if final_ans.get("reference"):
                canvas.reference.append(final_ans["reference"])
            conv.dsl = json.loads(str(canvas))
            API4ConversationService.append_message(conv.id, conv.to_dict())
        except Exception as e:
            traceback.print_exc()
            error_message = str(e)
            conv.dsl = json.loads(str(canvas))
            API4ConversationService.append_message(conv.id, conv.to_dict())
            print(f"错误信息: {error_message}")
            # 检查是否是PhotoDescribe组件的特定输入校验错误
            if "未检测到图像输入" in error_message or "检测到多个图像输入" in error_message:
                # 将错误作为正常回复返回给用户
                current_time = time.time()
                assistant_error_message_obj = {
                    "role": "assistant", 
                    "content": error_message, 
                    "created_at": current_time, # 确保时间戳
                    "id": message_id # 确保ID，与用户消息对应
                }

                # 1. 添加到 canvas 内部消息列表 (用于画布状态)
                canvas.messages.append(assistant_error_message_obj)
                canvas.history.append(("assistant", error_message))
                
                # 2. 添加到会话顶层消息列表 (用于前端显示和持久化)
                if not conv.message: # 确保 conv.message 列表存在
                    conv.message = []
                conv.message.append(assistant_error_message_obj) # <--- 新增：直接添加到 conv.message
                
                # 更新 DSL 并保存
                conv.dsl = json.loads(str(canvas)) 
                API4ConversationService.append_message(conv.id, conv.to_dict())
                
                yield "data:" + json.dumps({"code": 0, "message": "",
                                           "data": {"answer": error_message, 
                                                    "reference": [], 
                                                    "id": message_id, # 确保响应中也包含id
                                                    "session_id": session_id}}, # 确保响应中包含session_id
                                          ensure_ascii=False) + "\n\n"
            else:
                # 其他错误仍然作为错误返回
                yield "data:" + json.dumps({"code": 500, "message": error_message,
                                           "data": {"answer": "**ERROR**: " + error_message, "reference": []}},
                                          ensure_ascii=False) + "\n\n"
        yield "data:" + json.dumps({"code": 0, "message": "", "data": True}, ensure_ascii=False) + "\n\n"

    else:
        try:
            for answer in canvas.run(stream=False):
                if answer.get("running_status"):
                    continue
                final_ans["content"] = "\n".join(answer["content"]) if "content" in answer else ""
                canvas.messages.append({"role": "assistant", "content": final_ans["content"], "id": message_id})
                if final_ans.get("reference"):
                    canvas.reference.append(final_ans["reference"])
                conv.dsl = json.loads(str(canvas))

                result = {"answer": final_ans["content"], "reference": final_ans.get("reference", [])}
                result = structure_answer(conv, result, message_id, session_id)
                API4ConversationService.append_message(conv.id, conv.to_dict())
                yield result
                break
        except Exception as e:
            traceback.print_exc()
            error_message = str(e)
            conv.dsl = json.loads(str(canvas))
            API4ConversationService.append_message(conv.id, conv.to_dict())
            
            # 检查是否是PhotoDescribe组件的特定输入校验错误
            if "未检测到图像输入" in error_message or "检测到多个图像输入" in error_message:
                # 将错误消息添加到会话历史
                canvas.messages.append({"role": "assistant", "content": error_message, "created_at": time.time(), "id": message_id})
                canvas.history.append(("assistant", error_message))
                # 保存更新后的会话
                conv.dsl = json.loads(str(canvas))
                API4ConversationService.append_message(conv.id, conv.to_dict())
                
                # 将错误作为正常回复返回
                result = {"answer": error_message, "reference": []}
                result = structure_answer(conv, result, message_id, session_id)
                yield result
            else:
                # 其他错误返回错误信息
                result = {"answer": "**ERROR**: " + error_message, "reference": []}
                result = structure_answer(conv, result, message_id, session_id)
                yield result