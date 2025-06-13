from flask import request, Response
from flask_login import login_required, current_user
from api.utils.api_utils import get_json_result, server_error_response, get_data_error_result, token_required, validate_request
from api.db.db_models import ChatBot, ChatBotConversation, UserCanvas
from agent.canvas import Canvas
# from api.db.services.conversation_service import structure_answer
from api.db.services.canvas_service import UserCanvasService
from api.db.services.api_service import API4ConversationService
from api.utils.api_utils import get_result, get_error_data_result
import uuid
import json
import time
from uuid import uuid4
from api.utils import get_uuid

# 获取当前Agent所绑定的所有Chatbot
@manager.route('/list/<agent_id>', methods=['GET'])
@login_required
def get_chatbot_list(agent_id):
    try:
        user_id = current_user.id
        chatbots = ChatBot.select().where(ChatBot.canvas_id == agent_id)

        chatbot_info = [{
            'client_id': chatbot.client_id,
            'canvas_id': chatbot.canvas_id,
            'user_id': chatbot.user_id,
            'client_secret': chatbot.client_secret,
            'status': chatbot.status
        } for chatbot in chatbots]

        return get_json_result(data=chatbot_info)
        
    except Exception as e:
        return server_error_response(e)

# 添加绑定
@manager.route('/add', methods=['POST'])
@login_required
@validate_request("canvas_id", "client_id", "client_secret")
def add_chatbot():
    req = request.json
    canvas_id = req.get('canvas_id')
    client_id = req.get('client_id')
    client_secret = req.get('client_secret')

    user_id = current_user.id

    try:
        exists = ChatBot.select().where(
            ChatBot.client_id == client_id,
            ChatBot.user_id == user_id
        ).exists()

        if exists:
            return get_data_error_result(message="Chatbot already exists!")
        
        ChatBot.create(
            client_id=client_id,
            user_id=user_id,
            canvas_id=canvas_id,
            client_secret=client_secret,
            status="stop"
        )
        return get_json_result(data={"message": "success"})
    except Exception as e:
        return server_error_response(e)

# 删除绑定
@manager.route('/delete/<client_id>', methods=['DELETE'])
@login_required
def delete_chatbot(client_id):
    try:
        user_id = current_user.id
        chatbot = ChatBot.get(ChatBot.client_id == client_id, ChatBot.user_id == user_id)
        if not chatbot:
            return get_data_error_result(message="Chatbot not found!")
        chatbot.delete_instance()
        return get_json_result(data={"message": "success"})
    except Exception as e:
        return server_error_response(e)

# 聊天接口
@manager.route('/chat', methods=['POST'])
@validate_request("client_id", "question", "chat_type")
def chat_with_bot():
    try:
        req = request.json
        client_id = req.get('client_id')
        question = req.get('question', '')
        chat_type = req.get('chat_type')  # 'group' 或 'private'
        
        # 获取或设置默认user_id
        message_from_id = req.get('message_from_id')
        
        # 验证chatbot存在
        try:
            chatbot = ChatBot.get(ChatBot.client_id == client_id)
        except ChatBot.DoesNotExist:
            return get_data_error_result(message="Chatbot not found!")
        
        # 获取对应的canvas
        canvas_id = chatbot.canvas_id
        user_id = chatbot.user_id
        
        # 查询canvas
        cvs = UserCanvasService.query(id=canvas_id)
        if not cvs:
            return get_data_error_result(message=f"Canvas {canvas_id} not found!")
        
        try:
            for answer in completion(user_id, canvas_id, client_id, message_from_id, question, chat_type):
                return get_result(data=answer)
        except Exception as e:
            return get_error_data_result(str(e))
        
    except Exception as e:
        print(f"聊天接口异常: {str(e)}")
        return server_error_response(e)
    

def completion(tenant_id, agent_id, client_id, message_from_id, question, chat_type, session_id=None, **kwargs):
    e, cvs = UserCanvasService.get_by_id(agent_id)
    assert e, "Agent not found."
    # assert cvs.user_id == tenant_id, "You do not own the agent."
    if not isinstance(cvs.dsl,str):
        cvs.dsl = json.dumps(cvs.dsl, ensure_ascii=False)
    canvas = Canvas(cvs.dsl, tenant_id)
    message_id = str(uuid4())
    # e, conv = API4ConversationService.get_by_id(session_id)
    # assert e, "Session not found!"
    
    # 检查是否有预设参数，如果有，则执行完整的流程
    query = canvas.get_preset_param()
    print("当前有预设参数：", query)
    
    # 先清空当前消息以准备加载历史消息
    canvas.messages = []
    canvas.history = []
    
    conv = cvs
    conv.message = []
    if chat_type == 'private':
        try:
            chatbot_conv = ChatBotConversation.get(ChatBotConversation.user_id == message_from_id, ChatBotConversation.client_id == client_id)
            if chatbot_conv and chatbot_conv.message:
                conv.message = chatbot_conv.message
                # 将历史消息加载到canvas中
                for msg in conv.message:
                    canvas.messages.append(msg)
                    # 同时添加到history中，因为canvas.run使用history而非messages
                    if msg["role"] == "user":
                        canvas.add_user_input(msg["content"])
                    elif msg["role"] == "assistant":
                        canvas.history.append(("assistant", msg["content"]))
        except ChatBotConversation.DoesNotExist:
            # 如果聊天记录不存在，就使用空列表
            pass
    
    # 添加当前用户消息
    conv.message.append({
        "role": "user",
        "content": question,
        "id": message_id
    })
    
    # 添加当前用户消息到canvas
    canvas.messages.append({"role": "user", "content": question, "id": message_id})
    canvas.add_user_input(question)
    
    # 关键修改：如果存在预设参数，并且这是第一次用户消息，则跳过Begin组件的执行
    user_messages = [msg for msg in conv.message if msg["role"] == "user"]
    if query and len(user_messages) == 1:
        # 手动设置path，跳过Begin组件的执行
        canvas.path = [["begin"], []]
        # 获取Begin组件的下游组件
        downstream = canvas.components["begin"]["downstream"]
        # 将下游组件添加到path中
        canvas.path[-1].extend(downstream)

    final_ans = {"reference": [], "content": ""}

    for answer in canvas.run(stream=False):
        if answer.get("running_status"):
            continue
        final_ans["content"] = "\n".join(answer["content"]) if "content" in answer else ""
        canvas.messages.append({"role": "assistant", "content": final_ans["content"], "id": message_id})
        # 同时添加到history中
        canvas.history.append(("assistant", final_ans["content"]))
        # if final_ans.get("reference"):
        #     canvas.reference.append(final_ans["reference"])
        conv.dsl = json.loads(str(canvas))

        result = {"answer": final_ans["content"], "reference": final_ans.get("reference", [])}
        result = structure_answer(conv, result, message_id, session_id)
        # API4ConversationService.append_message(conv.id, conv.to_dict())
        # 私聊的话就保存对话历史
        if chat_type == 'private':
            try:
                chatbot_conv = ChatBotConversation.get(ChatBotConversation.user_id == message_from_id, ChatBotConversation.client_id == client_id)
                chatbot_conv.message = conv.message
                chatbot_conv.save()
            except ChatBotConversation.DoesNotExist:
                # 如果不存在，则创建一个新的
                chat_conv_id = uuid.uuid4().hex
                new_chat_conv = ChatBotConversation.create(
                    id=chat_conv_id,
                    user_id=message_from_id,
                    client_id=client_id,
                    message=conv.message
                )

        yield result
        break

def structure_answer(conv, ans, message_id, session_id):
    reference = ans["reference"]
    if not isinstance(reference, dict):
        reference = {}
        ans["reference"] = {}

    # chunk_list = chunks_format(reference)

    # reference["chunks"] = chunk_list
    ans["id"] = message_id
    ans["session_id"] = session_id

    if not conv:
        return ans

    if not conv.message:
        conv.message = []
    if not conv.message or conv.message[-1].get("role", "") != "assistant":
        conv.message.append({"role": "assistant", "content": ans["answer"], "created_at": time.time(), "id": message_id})
    else:
        conv.message[-1] = {"role": "assistant", "content": ans["answer"], "created_at": time.time(), "id": message_id}
    # if conv.reference:
    #     conv.reference[-1] = reference
    return ans