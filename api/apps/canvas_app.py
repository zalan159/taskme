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
import traceback
from flask import request, Response
from flask_login import login_required, current_user
from api.db.services.canvas_service import CanvasTemplateService, UserCanvasService, CanvasInfoService
from api.db import CanvasPermissions, StatusEnum
from api.settings import RetCode
from api.utils import get_uuid
from api.utils.api_utils import get_json_result, server_error_response, validate_request, get_data_error_result
from agent.canvas import Canvas
from peewee import MySQLDatabase, PostgresqlDatabase
from api.db.db_models import APIToken, CanvasInfo, CanvasTenant
from api.db.services.user_service import UserTenantService
from api.db.services.knowledgebase_service import KnowledgebaseService
import uuid
import logging

@manager.route('/add_multi_canvas', methods=['POST'])  # noqa: F821
def add_multi_canvas():
    try:
        req = request.json
        industry = req.get("industry")
        canvas_data = req.get("canvas_data", [])
        
        if not canvas_data:
            return get_data_error_result(message="No canvas data provided")

        base_canvas_data = {
                            'dsl': {'graph': {'nodes': [{'id': 'begin', 'type': 'beginNode', 'position': {'x': 50, 'y': 200}, 'data': {'label': 'Begin', 'name': 'begin'}, 'sourcePosition': 'left', 'targetPosition': 'right'}], 'edges': []}, 'components': {'begin': {'obj': {'component_name': 'Begin', 'params': {}}, 'downstream': ['Answer:China'], 'upstream': []}}, 'messages': [], 'reference': [], 'history': [], 'path': [], 'answer': []}, 
                            'user_id': "7ef84479fd9611ef95594dcc9a6fb737", 
                        }
            
        for canvas in canvas_data:
            c_id = uuid.uuid4().hex
            name = canvas.get("name")
            tags = canvas.get("tags", [])
            
            # 1. 先创建 user_canvas 记录
            canvas_data = {
                **base_canvas_data,
                'title': name,
                'id': c_id
            }
            UserCanvasService.save(**canvas_data)
            
            # 2. 再创建 canvas_info 记录
            CanvasInfo.create(
                canvas_id=c_id,
                canvas_permissions="private",
                canvas_tag=tags,
                canvas_industry=industry
            )
            
        return get_json_result(data=True)
    except Exception as e:
        return get_data_error_result(message=f"Failed to add multi canvas: {str(e)}")
    
def check_canvas_kb_permission(canvas_id):
    try:
        status, canvas_detial = UserCanvasService.get_by_id(canvas_id)
        if not status:
            return False, "Canvas not found"
        
        canvas_data = canvas_detial.dsl
        if not canvas_data:
            return False, "Canvas data not found"
        
        # 查找包含Retrieval字段的组件
        kb_ids = []
        components = canvas_data.get("components", {})
        for component_id, component_data in components.items():
            if "Retrieval" in component_id:
                params = component_data.get("obj", {}).get("params", {})
                if "kb_ids" in params:
                    kb_ids.extend(params["kb_ids"])
        
        canvas_info = CanvasInfo.get_or_none(CanvasInfo.canvas_id == canvas_id)
        if not canvas_info:
            return False, "Canvas Info not found"
        canvas_permission = canvas_info.canvas_permissions
        
        # 定义权限等级映射
        canvas_permission_level = {
            'public': 3,
            'team': 2,
            'private': 1
        }
        
        kb_permission_level = {
            'public': 3,
            'team': 2,
            'me': 1
        }
        
        canvas_level = canvas_permission_level.get(canvas_permission, 0)
        
        for kb in kb_ids:
            e, kb_data = KnowledgebaseService.get_by_id(kb)
            if not e:
                return False, "Knowledgebase not found"
            
            # 直接从kb_data对象获取permission属性
            kb_permission = kb_data.permission if hasattr(kb_data, 'permission') else 'me'
            kb_level = kb_permission_level.get(kb_permission, 0)
            
            # 如果知识库权限小于canvas权限，更新知识库权限
            if kb_level < canvas_level:
                # 将canvas权限映射到知识库权限
                new_kb_permission = {
                    'public': 'public',
                    'team': 'team',
                    'private': 'me'
                }.get(canvas_permission)
                
                # 更新知识库权限
                kb_data.permission = new_kb_permission
                kb_data.save()

        return True, kb_ids
    except Exception as e:
        return False, f"Error checking canvas kb permission: {str(e)}"

def check_user_permission(canvas_id, user_id):
    try:
        # 1. 获取 canvas 信息
        canvas_info = CanvasInfo.get_or_none(CanvasInfo.canvas_id == canvas_id)
        if not canvas_info:
            return False, "Canvas not found"
            
        # 2. 检查权限
        # 如果是公共的，直接允许访问
        if canvas_info.canvas_permissions == CanvasPermissions.PUBLIC.value:
            return True, None
            
        # 如果是私有的，检查是否是创建者
        canvas = UserCanvasService.get_or_none(id=canvas_id)
        if not canvas:
            return False, "Canvas not found"
            
        if canvas_info.canvas_permissions == CanvasPermissions.PRIVATE.value:
            if canvas.user_id == user_id:
                return True, None
            return False, "No permission: private canvas"
            
        # 如果是团队的，检查是否在同一个团队
        if canvas_info.canvas_permissions == CanvasPermissions.TEAM.value:
            # 获取 canvas 所属的团队
            canvas_teams = CanvasTenant.select().where(CanvasTenant.canvas_id == canvas_id)
            canvas_team_ids = [ct.tenant_id for ct in canvas_teams]
            
            # 获取用户所在的团队
            user_tenants = UserTenantService.get_tenants_by_user_id(user_id)
            user_team_ids = [t['tenant_id'] for t in user_tenants]
            
            # 检查是否有交集
            if set(canvas_team_ids) & set(user_team_ids):
                return True, None
            return False, "No permission: not in the same team"
            
        return False, "Invalid permission type"
        
    except Exception as e:
        return False, f"Error checking permission: {str(e)}"

@manager.route('/templates', methods=['GET'])  # noqa: F821
@login_required
def templates():
    return get_json_result(data=[c.to_dict() for c in CanvasTemplateService.get_all()])


@manager.route('/list', methods=['GET'])  # noqa: F821
@login_required
def canvas_list():
    # return get_json_result(data=sorted([c.to_dict() for c in \
                    #         UserCanvasService.query(user_id=current_user.id)], key=lambda x: x["update_time"]*-1)
                    # )

    try:
        # 1. 获取用户自己的canvas
        user_canvases = UserCanvasService.query(user_id=current_user.id)
        user_canvas_ids = [c.id for c in user_canvases]
        
        # 2. 获取团队canvas (canvas_permissions = 'team')
        team_canvases = []
        tenants = UserTenantService.get_tenants_by_user_id(current_user.id)
        if tenants:
            for tenant in tenants:
                canvas_tenants = CanvasTenant.select().where(CanvasTenant.tenant_id == tenant['tenant_id'])
                for c in canvas_tenants:
                    canvas = UserCanvasService.get_or_none(id=c.canvas_id)
                    if canvas and canvas.id not in user_canvas_ids:  # 排除用户自己的canvas
                        team_canvases.append(canvas)
        else:
            print("没有团队")
        
        # 3. 获取公共canvas (canvas_permissions = 'public')
        public_canvases = []
        public_canvas_infos = CanvasInfo.select().where(CanvasInfo.canvas_permissions == 'public')
        for info in public_canvas_infos:
            canvas = UserCanvasService.get_or_none(id=info.canvas_id)
            if canvas and canvas.id not in user_canvas_ids:  # 排除用户自己的canvas
                public_canvases.append(canvas)
        
        # 4. 合并结果并按更新时间排序
        all_canvases = []
        # 添加用户自己的canvas
        # all_canvases.extend([{"canvas": c.to_dict(), "type": "personal"} for c in user_canvases])
        # # 添加团队canvas
        # all_canvases.extend([{"canvas": c.to_dict(), "type": "team"} for c in team_canvases])
        # # 添加公共canvas
        # all_canvases.extend([{"canvas": c.to_dict(), "type": "public"} for c in public_canvases])

        # 返回所有canvas
        all_canvases.extend([{**c.to_dict(), "user_id": c.user_id} for c in user_canvases])
        all_canvases.extend([{**c.to_dict(), "user_id": c.user_id} for c in team_canvases])
        all_canvases.extend([{**c.to_dict(), "user_id": c.user_id} for c in public_canvases])
        
        # 按更新时间降序排序
        sorted_canvases = sorted(all_canvases, key=lambda x: x["update_time"]*-1)
        
        return get_json_result(data=sorted_canvases)
        
    except Exception as e:
        return get_data_error_result(message=f"Failed to get canvas list: {str(e)}")

def update_canvas_info(canvas_id, canvas_tag, canvas_permissions, canvas_industry, team_ids=None, is_recommended=None):
    # Validate canvas_tag if provided
    if canvas_tag is not None: # Validate only if canvas_tag is actually provided
        try:
            if isinstance(canvas_tag, str):
                tag_data = json.loads(canvas_tag)
            else:
                tag_data = canvas_tag
            if not isinstance(tag_data, list):
                logging.error(f"[UpdateCanvasInfo] canvas_tag validation failed for {canvas_id}: not a list.")
                return False, "canvas_tag must be a JSON array"
        except json.JSONDecodeError:
            logging.error(f"[UpdateCanvasInfo] canvas_tag JSONDecodeError for {canvas_id}.")
            return False, "canvas_tag must be a valid JSON array"
    
    existing_info = CanvasInfo.get_or_none(CanvasInfo.canvas_id == canvas_id)
    if existing_info:
        logging.info(f"[UpdateCanvasInfo] Attempting to update Agent ID: {canvas_id}. Request params: tags={canvas_tag is not None}, perms={canvas_permissions is not None}, industry={canvas_industry is not None}, recommend={is_recommended}, team_ids={team_ids is not None}")
        
        old_permission = existing_info.canvas_permissions # Store old permission for team logic
        made_changes = False

        # Update fields only if they are provided in the request
        if canvas_tag is not None:
            if existing_info.canvas_tag != canvas_tag:
                existing_info.canvas_tag = canvas_tag
                logging.info(f"[UpdateCanvasInfo] Agent ID: {canvas_id} - canvas_tag updated.")
                made_changes = True
        
        if canvas_permissions is not None:
            if existing_info.canvas_permissions != canvas_permissions:
                existing_info.canvas_permissions = canvas_permissions
                logging.info(f"[UpdateCanvasInfo] Agent ID: {canvas_id} - canvas_permissions updated to {canvas_permissions}.")
                made_changes = True

        if canvas_industry is not None:
            if existing_info.canvas_industry != canvas_industry:
                existing_info.canvas_industry = canvas_industry
                logging.info(f"[UpdateCanvasInfo] Agent ID: {canvas_id} - canvas_industry updated.")
                made_changes = True

        if is_recommended is not None: 
            if existing_info.is_recommended != is_recommended:
                existing_info.is_recommended = is_recommended
                logging.info(f"[UpdateCanvasInfo] Agent ID: {canvas_id} - is_recommended updated to {is_recommended}.")
                made_changes = True
        
        if made_changes:
            existing_info.save()
            logging.info(f"[UpdateCanvasInfo] Agent ID: {canvas_id} - Saved changes. Current state: tags={existing_info.canvas_tag}, perms={existing_info.canvas_permissions}, industry={existing_info.canvas_industry}, recommended={existing_info.is_recommended}")
        else:
            logging.info(f"[UpdateCanvasInfo] Agent ID: {canvas_id} - No actual changes to save for core fields.")
        
        # Handle canvas_tenant table updates (only if permissions actually changed and were provided)
        if canvas_permissions is not None and old_permission != canvas_permissions:
            logging.info(f"[UpdateCanvasInfo] Agent ID: {canvas_id} - Permission changed from '{old_permission}' to '{canvas_permissions}'. Handling team associations.")
            if old_permission == 'team' and canvas_permissions != 'team':
                logging.info(f"[UpdateCanvasInfo] Agent ID: {canvas_id} - Permission changed from team to non-team. Removing team associations.")
                CanvasTenant.delete().where(CanvasTenant.canvas_id == canvas_id).execute()
            elif canvas_permissions == 'team':
                logging.info(f"[UpdateCanvasInfo] Agent ID: {canvas_id} - Permission changed to team. Updating team associations.")
                CanvasTenant.delete().where(CanvasTenant.canvas_id == canvas_id).execute() # Clear existing
                if team_ids:
                    for team_id in team_ids:
                        CanvasTenant.create(
                            id=get_uuid(),
                            canvas_id=canvas_id,
                            tenant_id=team_id
                        )
                    logging.info(f"[UpdateCanvasInfo] Agent ID: {canvas_id} - Associated with teams: {team_ids}.")
                else:
                    logging.warning(f"[UpdateCanvasInfo] Agent ID: {canvas_id} - Permission set to team, but no team_ids provided. No teams associated.")
        
        return True, None
    else:
        logging.warning(f"[UpdateCanvasInfo] CanvasInfo record not found for update, canvas_id: {canvas_id}")
        return False, "Canvas not found"

# 获取Agent信息
@manager.route('/get_agent_info', methods=['GET'])  # noqa: F821
# @login_required
def get_agent_info():
    canvas_id = request.args.get("canvas_id")
    canvas_info = CanvasInfo.get_or_none(CanvasInfo.canvas_id == canvas_id)
    if canvas_info:
        # 获取团队ID列表
        team_ids = []
        if canvas_info.canvas_permissions == 'team':
            canvas_tenants = CanvasTenant.select().where(CanvasTenant.canvas_id == canvas_id)
            team_ids = [ct.tenant_id for ct in canvas_tenants]

        # 获取canvas的创建者ID
        canvas = UserCanvasService.get_or_none(id=canvas_id)
        user_id = canvas.user_id if canvas else None
        # print("Canvas user_id:", user_id)  # 旧的日志

        canvas_info_dict = {
            "canvas_id": canvas_info.canvas_id,
            "canvas_tag": canvas_info.canvas_tag,
            "canvas_permissions": canvas_info.canvas_permissions,
            "canvas_industry": canvas_info.canvas_industry,
            "team_ids": team_ids,
            "user_id": user_id,
            "is_recommended": canvas_info.is_recommended # 添加 is_recommended 字段
        }
        logging.info(f"[GetAgentInfo API] 返回的 canvas_info_dict (agentId: {canvas_id}): {canvas_info_dict}") # 添加日志
        return get_json_result(data=canvas_info_dict)
    else:
        logging.warning(f"[GetAgentInfo API] 未找到 CanvasInfo，canvas_id: {canvas_id}") # 添加日志
        return get_data_error_result(message="Canvas not found")

# 设置Agent信息
@manager.route('/set_agent_info', methods=['POST'])  # noqa: F821
# @login_required
def set_agent_info():
    # 获取请求数据
    req = request.json
    print(req)
    
    # 验证必需参数
    if 'canvas_id' not in req:
        return get_data_error_result(message="canvas_id is required")
    
    # 检查用户是否是Agent的创建者
    canvas = UserCanvasService.get_or_none(id=req['canvas_id'])
    if not canvas:
        return get_data_error_result(message="Canvas not found")
    
    if canvas.user_id != current_user.id:
        return get_data_error_result(message="Only the creator can modify agent permissions")
    
    # 验证permissions参数
    if 'canvas_permissions' in req:
        if req['canvas_permissions'] not in [e.value for e in CanvasPermissions]:
            return get_data_error_result(
                message=f"Invalid permissions value. Must be one of: {', '.join([e.value for e in CanvasPermissions])}"
            )
        
        # 如果权限为team，验证team_ids
        if req['canvas_permissions'] == 'team':
            if 'team_ids' not in req or not req['team_ids']:
                return get_data_error_result(message="team_ids is required when permission is 'team'")
            if not isinstance(req['team_ids'], list):
                return get_data_error_result(message="team_ids must be a list")
    
    try:
        success, error_message = update_canvas_info(
            req['canvas_id'], 
            req.get('canvas_tag'), 
            req.get('canvas_permissions'), 
            req.get('canvas_industry'),
            req.get('team_ids'),  # 添加team_ids参数
            req.get('is_recommended') # 添加is_recommended参数
        )
        if success:
            # 检查canvas是否关联了kb
            status, data = check_canvas_kb_permission(req['canvas_id'])
            if not status:
                return get_data_error_result(message=data)
    
            return get_json_result(data={"message": "Canvas info updated successfully"})
        else:
            return get_data_error_result(message=error_message)
        
    except Exception as e:
        return get_data_error_result(message=f"Failed to update canvas info: {str(e)}")

@manager.route('/rm', methods=['POST'])  # noqa: F821
@validate_request("canvas_ids")
@login_required
def rm():
    for i in request.json["canvas_ids"]:
        if not UserCanvasService.query(user_id=current_user.id,id=i):
            return get_json_result(
                data=False, message='Only owner of canvas authorized for this operation.',
                code=RetCode.OPERATING_ERROR)
        UserCanvasService.delete_by_id(i)
    return get_json_result(data=True)


@manager.route('/set', methods=['POST'])  # noqa: F821
@validate_request("dsl", "title")  # 验证请求必须包含dsl和title字段
@login_required  # 需要登录才能访问
def save():
    # 获取请求的JSON数据
    req = request.json
    # 添加当前用户ID到请求数据中
    req["user_id"] = current_user.id

    # 如果dsl不是字符串类型，将其转换为JSON字符串
    if not isinstance(req["dsl"], str):
        req["dsl"] = json.dumps(req["dsl"], ensure_ascii=False)

    # 将dsl字符串解析回JSON对象
    req["dsl"] = json.loads(req["dsl"])

    # 如果请求中没有id字段，说明是创建新的画布
    if "id" not in req:
        # 检查当前用户是否已经有同名的画布
        if UserCanvasService.query(user_id=current_user.id, title=req["title"].strip()):
            return get_data_error_result(message=f"{req['title'].strip()} already exists.")
        
        # 生成新的UUID作为画布ID
        req["id"] = get_uuid()
        # 保存新画布，如果保存失败返回错误信息
        if not UserCanvasService.save(**req):
            return get_data_error_result(message="Fail to save canvas.")
        else:
            # 保存成功后，添加新纪录在CanvasInfo表
            CanvasInfo.create(canvas_id=req["id"], canvas_permissions="private", canvas_tag=[])
    else:
        # 如果请求中有id字段，说明是更新已有画布
        # 检查当前用户是否是画布的所有者
        # if not UserCanvasService.query(user_id=current_user.id, id=req["id"]):
        #     return get_json_result(
        #         data=False, 
        #         message='Only owner of canvas authorized for this operation.',
        #         code=RetCode.OPERATING_ERROR)
        can_edit, msg = check_user_permission(req["id"], current_user.id)
        if not can_edit:
            return get_data_error_result(message=msg)
        # 更新画布内容
        UserCanvasService.update_by_id(req["id"], req)

    # 检查canvas是否关联了kb
    status, data = check_canvas_kb_permission(req["id"])
    if not status:
        return get_data_error_result(message="Fail to check canvas kb permission")
    
    # 返回成功结果，包含更新后的画布数据
    return get_json_result(data=req)


@manager.route('/get/<canvas_id>', methods=['GET'])  # noqa: F821
@login_required
def get(canvas_id):
    e, c = UserCanvasService.get_by_id(canvas_id)
    if not e:
        return get_data_error_result(message="canvas not found.")
    return get_json_result(data=c.to_dict())

@manager.route('/getsse/<canvas_id>', methods=['GET'])  # type: ignore # noqa: F821
def getsse(canvas_id):
    token = request.headers.get('Authorization').split()
    if len(token) != 2:
        return get_data_error_result(message='Authorization is not valid!"')
    token = token[1]
    objs = APIToken.query(beta=token)
    if not objs:
        return get_data_error_result(message='Authentication error: API key is invalid!"')
    e, c = UserCanvasService.get_by_id(canvas_id)
    if not e:
        return get_data_error_result(message="canvas not found.")
    return get_json_result(data=c.to_dict())

@manager.route('/completion', methods=['POST'])  # noqa: F821
@validate_request("id")
@login_required
def run():
    # 添加请求日志
    print(f"[Canvas Debug] 收到请求")
    
    req = request.json
    print(f"[Canvas Debug] 请求参数: id={req.get('id')}, message={req.get('message', '')[:50]}...")
    if 'images' in req:
        print(f"[Canvas Debug] 收到图片数量: {len(req['images'])}")
        for i, img in enumerate(req['images']):
            print(f"[Canvas Debug] 图片{i+1}: name={img.get('name')}, data长度={len(img.get('data', ''))}")
    
    stream = req.get("stream", True)
    e, cvs = UserCanvasService.get_by_id(req["id"])
    if not e:
        return get_data_error_result(message="canvas not found.")
    if not UserCanvasService.query(user_id=current_user.id, id=req["id"]):
        return get_json_result(
            data=False, message='Only owner of canvas authorized for this operation.',
            code=RetCode.OPERATING_ERROR)

    if not isinstance(cvs.dsl, str):
        cvs.dsl = json.dumps(cvs.dsl, ensure_ascii=False)

    final_ans = {"reference": [], "content": ""}
    message_id = req.get("message_id", get_uuid())
    try:
        canvas = Canvas(cvs.dsl, current_user.id)
        
        # 处理文本消息
        if "message" in req:
            canvas.messages.append({"role": "user", "content": req["message"], "id": message_id})
            canvas.add_user_input(req["message"])
            print(f"[Canvas Debug] 添加用户文本输入: {req['message'][:50]}...")
        
        # 处理图片输入
        if "images" in req and isinstance(req["images"], list):
            print(f"[Canvas Debug] 处理{len(req['images'])}张图片")
            # 更新消息中添加图片
            if "message" in req:
                # 找到刚刚添加的消息并更新
                for msg in canvas.messages:
                    if msg.get("id") == message_id:
                        msg["images"] = req["images"]
                        print(f"[Canvas Debug] 更新消息{message_id}，添加图片")
                        break
            else:
                # 如果没有文本消息，创建一个只包含图片的消息
                canvas.messages.append({
                    "role": "user", 
                    "content": "", 
                    "images": req["images"],
                    "id": message_id,
                    # 使用一致的键名"images"
                    "images": req.get("images", []) 
                })
                print(f"[Canvas Debug] 创建新消息{message_id}，只包含图片")
            
            # 处理每张图片
            for idx, img in enumerate(req["images"]):
                img_data = img.get("data", "")
                img_name = img.get("name", f"image{idx+1}")
                if img_data:
                    # 添加图片到画布
                    print(f"[Canvas Debug] 添加图片{idx+1}: {img_name}，数据长度: {len(img_data)}")
                    canvas.add_image_input(img_data, img_name)
                else:
                    print(f"[Canvas Debug] 图片{idx+1}数据为空")
        else:
            print(f"[Canvas Debug] 请求中没有图片数据")
    except Exception as e:
        print(f"[Canvas Error] 处理请求异常: {str(e)}")
        print(f"异常堆栈:\n{traceback.format_exc()}")
        return server_error_response(e)

    if stream:
        def sse():
            try:
                # print("[Canvas Debug] 进入流式响应处理")
                for ans in canvas.run(stream=True):
                    print(f"[Canvas Debug] 收到流数据: {json.dumps(ans, ensure_ascii=False)[:200]}...")
                    if ans.get("running_status"):
                        print("[Canvas Debug] 发送运行状态更新")
                        yield "data:" + json.dumps({"code": 0, "message": "",
                                                    "data": {"answer": ans["content"],
                                                             "running_status": True}},
                                                   ensure_ascii=False) + "\n\n"
                        continue
                    print("[Canvas Debug] 发送常规响应块")
                    for k in ans.keys():
                        final_ans[k] = ans[k]
                    ans = {"answer": ans["content"], "reference": ans.get("reference", [])}
                    yield "data:" + json.dumps({"code": 0, "message": "", "data": ans}, ensure_ascii=False) + "\n\n"
                
                print("[Canvas Debug] 流处理完成，更新画布状态")
                canvas.messages.append({"role": "assistant", "content": final_ans["content"], "id": message_id})
                canvas.history.append(("assistant", final_ans["content"]))
                if not canvas.path[-1]:
                    canvas.path.pop(-1)
                if final_ans.get("reference"):
                    canvas.reference.append(final_ans["reference"])
                cvs.dsl = json.loads(str(canvas))
                UserCanvasService.update_by_id(req["id"], cvs.to_dict())
            except Exception as e:
                import traceback
                print(f"[Canvas Error] 流处理异常: {str(e)}")
                print(f"异常堆栈:\n{traceback.format_exc()}")
                cvs.dsl = json.loads(str(canvas))
                if not canvas.path[-1]:
                    canvas.path.pop(-1)
                UserCanvasService.update_by_id(req["id"], cvs.to_dict())
                yield "data:" + json.dumps({"code": 500, "message": str(e),
                                            "data": {"answer": "**ERROR**: " + str(e), "reference": []}},
                                           ensure_ascii=False) + "\n\n"
            finally:
                print("[Canvas Debug] 流处理结束")

        resp = Response(sse(), mimetype="text/event-stream")
        print("[Canvas Debug] 返回SSE响应对象")
        resp.headers.add_header("Cache-control", "no-cache")
        resp.headers.add_header("Connection", "keep-alive")
        resp.headers.add_header("X-Accel-Buffering", "no")
        resp.headers.add_header("Content-Type", "text/event-stream; charset=utf-8")
        return resp

    for answer in canvas.run(stream=False):
        if answer.get("running_status"):
            continue
        final_ans["content"] = "\n".join(answer["content"]) if "content" in answer else ""
        canvas.messages.append({"role": "assistant", "content": final_ans["content"], "id": message_id})
        if final_ans.get("reference"):
            canvas.reference.append(final_ans["reference"])
        cvs.dsl = json.loads(str(canvas))
        UserCanvasService.update_by_id(req["id"], cvs.to_dict())
        return get_json_result(data={"answer": final_ans["content"], "reference": final_ans.get("reference", [])})


@manager.route('/reset', methods=['POST'])  # noqa: F821
@validate_request("id")
@login_required
def reset():
    req = request.json
    try:
        e, user_canvas = UserCanvasService.get_by_id(req["id"])
        if not e:
            return get_data_error_result(message="canvas not found.")
        if not UserCanvasService.query(user_id=current_user.id, id=req["id"]):
            return get_json_result(
                data=False, message='Only owner of canvas authorized for this operation.',
                code=RetCode.OPERATING_ERROR)

        canvas = Canvas(json.dumps(user_canvas.dsl), current_user.id)
        canvas.reset()
        req["dsl"] = json.loads(str(canvas))
        UserCanvasService.update_by_id(req["id"], {"dsl": req["dsl"]})
        return get_json_result(data=req["dsl"])
    except Exception as e:
        return server_error_response(e)


@manager.route('/input_elements', methods=['GET'])  # noqa: F821
@login_required
def input_elements():
    cvs_id = request.args.get("id")
    cpn_id = request.args.get("component_id")
    try:
        e, user_canvas = UserCanvasService.get_by_id(cvs_id)
        if not e:
            return get_data_error_result(message="canvas not found.")
        if not UserCanvasService.query(user_id=current_user.id, id=cvs_id):
            return get_json_result(
                data=False, message='Only owner of canvas authorized for this operation.',
                code=RetCode.OPERATING_ERROR)

        canvas = Canvas(json.dumps(user_canvas.dsl), current_user.id)
        return get_json_result(data=canvas.get_component_input_elements(cpn_id))
    except Exception as e:
        return server_error_response(e)


@manager.route('/debug', methods=['POST'])  # noqa: F821
@validate_request("id", "component_id", "params")
@login_required
def debug():
    req = request.json
    for p in req["params"]:
        assert p.get("key")
    try:
        e, user_canvas = UserCanvasService.get_by_id(req["id"])
        if not e:
            return get_data_error_result(message="canvas not found.")
        if not UserCanvasService.query(user_id=current_user.id, id=req["id"]):
            return get_json_result(
                data=False, message='Only owner of canvas authorized for this operation.',
                code=RetCode.OPERATING_ERROR)

        canvas = Canvas(json.dumps(user_canvas.dsl), current_user.id)
        canvas.get_component(req["component_id"])["obj"]._param.debug_inputs = req["params"]
        df = canvas.get_component(req["component_id"])["obj"].debug()
        return get_json_result(data=df.to_dict(orient="records"))
    except Exception as e:
        return server_error_response(e)


@manager.route('/test_db_connect', methods=['POST'])  # noqa: F821
@validate_request("db_type", "database", "username", "host", "port", "password")
@login_required
def test_db_connect():
    req = request.json
    try:
        if req["db_type"] in ["mysql", "mariadb"]:
            db = MySQLDatabase(req["database"], user=req["username"], host=req["host"], port=req["port"],
                               password=req["password"])
        elif req["db_type"] == 'postgresql':
            db = PostgresqlDatabase(req["database"], user=req["username"], host=req["host"], port=req["port"],
                                    password=req["password"])
        elif req["db_type"] == 'mssql':
            import pyodbc
            connection_string = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={req['host']},{req['port']};"
                f"DATABASE={req['database']};"
                f"UID={req['username']};"
                f"PWD={req['password']};"
            )
            db = pyodbc.connect(connection_string)
            cursor = db.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        else:
            return server_error_response("Unsupported database type.")
        if req["db_type"] != 'mssql':
            db.connect()
        db.close()
        
        return get_json_result(data="Database Connection Successful!")
    except Exception as e:
        return server_error_response(e)

