from flask import request
from flask_login import login_required, current_user
from api.db.services.canvas_service import UserCanvasService
from api.utils.api_utils import get_json_result, server_error_response, get_data_error_result, token_required
from api.db.db_models import APIToken, CanvasInfo, CanvasTenant
from api.db.services.user_service import UserTenantService


# 获取所有可用Agent
@manager.route('/get_all_agent', methods=['GET'])
@login_required
def get_all_agent():
    try:
        # user_id = request.args.get("user_id")
        user_id = current_user.id
        # 1. 获取用户自己的canvas
        user_canvases = UserCanvasService.query(user_id=user_id)
        user_canvas_ids = [c.id for c in user_canvases]
        
        # 2. 获取团队canvas (canvas_permissions = 'team')
        team_canvases = []
        tenants = UserTenantService.get_tenants_by_user_id(user_id)
        if tenants:
            for tenant in tenants:
                canvas_tenants = CanvasTenant.select().where(CanvasTenant.tenant_id == tenant['tenant_id'])
                for c in canvas_tenants:
                    canvas = UserCanvasService.get_or_none(id=c.canvas_id)
                    if canvas and canvas.id not in user_canvas_ids:  # 排除用户自己的canvas
                        team_canvases.append(canvas)
        
        # 3. 获取公共canvas (canvas_permissions = 'public')
        public_canvases = []
        public_canvas_infos = CanvasInfo.select().where(CanvasInfo.canvas_permissions == 'public')
        for info in public_canvas_infos:
            canvas = UserCanvasService.get_or_none(id=info.canvas_id)
            if canvas and canvas.id not in user_canvas_ids:  # 排除用户自己的canvas
                public_canvases.append(canvas)
        
        # 4. 合并所有canvas
        all_canvases = []
        all_canvases.extend([{**c.to_dict(), "user_id": c.user_id} for c in user_canvases])
        all_canvases.extend([{**c.to_dict(), "user_id": c.user_id} for c in team_canvases])
        all_canvases.extend([{**c.to_dict(), "user_id": c.user_id} for c in public_canvases])
        
        # 5. 按行业分类组织数据
        industry_data = {}
        for canvas in all_canvases:
            canvas_info = CanvasInfo.get_or_none(CanvasInfo.canvas_id == canvas['id'])
            if canvas_info and canvas_info.canvas_industry:
                industry = canvas_info.canvas_industry
                if industry not in industry_data:
                    industry_data[industry] = {
                        "categories": []
                    }
                
                # 根据canvas_tag确定category
                category_name = canvas_info.canvas_tag[0] if canvas_info.canvas_tag else "未分类"
                category = next((c for c in industry_data[industry]["categories"] if c["name"] == category_name), None)
                
                if not category:
                    category = {
                        "name": category_name,
                        "agents": []
                    }
                    industry_data[industry]["categories"].append(category)
                
                # 添加agent
                category["agents"].append({
                    "id": canvas['id'],
                    "name": canvas['title'],
                    "icon": canvas_info.icon  # 默认图标，可以根据需要修改
                })
        
        return get_json_result(data=industry_data)
        
    except Exception as e:
        return get_data_error_result(message=f"Failed to get canvas list: {str(e)}")


# 获取指定行业的Agent
@manager.route('/get_industry_canvas', methods=['POST'])  # noqa: F821
# @login_required
def get_industry_canvas():
    try:
        req = request.json
        industry = req.get("industry")
        
        if not industry:
            return get_data_error_result(message="Industry is required")
            
        # 查询指定行业的 Agent
        canvas_list = UserCanvasService.model.select(
            UserCanvasService.model.id,
            UserCanvasService.model.title,
            UserCanvasService.model.description,
            UserCanvasService.model.avatar,
            CanvasInfo.canvas_tag,
            CanvasInfo.canvas_permissions
        ).join(
            CanvasInfo,
            on=((UserCanvasService.model.id == CanvasInfo.canvas_id) & 
                (CanvasInfo.canvas_industry == industry))
        ).dicts()
        
        return get_json_result(data=list(canvas_list))
    except Exception as e:
        return server_error_response(e)


# 获取指定Agent的个性信息
@manager.route('/get_agent_info', methods=['GET'])  # noqa: F821
# @login_required
def get_agent_info():
    try:
        canvas_id = request.args.get("canvas_id")
        
        if not canvas_id:
            return get_data_error_result(message="Canvas ID is required")
        
        canvas = CanvasInfo.get_or_none(CanvasInfo.canvas_id == canvas_id)
        if not canvas:
            return get_data_error_result(message="Canvas not found")

        # 获取canvas的名字
        canvas_name = UserCanvasService.get_or_none(id=canvas_id).title
        
        # 获取canvas的信息
        canvas_info = {
            "canvas_id": canvas.canvas_id,
            "title": canvas_name,
            "icon": canvas.icon,
            "description": canvas.description,
            "placeholder_prompts": canvas.prompts["placeholderPrompts"],
            "sender_prompts": canvas.prompts["senderPrompts"]
        }
        
        return get_json_result(data=canvas_info)
    
    except Exception as e:
        return server_error_response(e)

# 获取指定Agent的详细信息
@manager.route('/get_agent_detail', methods=['GET'])  # noqa: F821
# @login_required
@token_required
def get_agent_detail(tenant_id):
    try:
        canvas_id = request.args.get("canvas_id")
        
        if not canvas_id:
            return get_data_error_result(message="Canvas ID is required")
        
        canvas = UserCanvasService.get_or_none(id=canvas_id)
        if not canvas:
            return get_data_error_result(message="Canvas not found")
        
        canvas_info = canvas.to_dict()
        return get_json_result(data=canvas_info)
    
    except Exception as e:
        return server_error_response(e)