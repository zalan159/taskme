from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import ChatBot
from app.core.process_manager import process_manager
from app.core.config import DEFAULT_BOT_URL
from typing import List, Optional
from pydantic import BaseModel

# 定义API路由
router = APIRouter()

# 依赖项
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic模型
class BotResponse(BaseModel):
    client_id: str
    status: str
    pid: Optional[int] = None

class BotsResponse(BaseModel):
    bots: List[BotResponse]

class BotLogResponse(BaseModel):
    client_id: str
    stdout: List[str]
    stderr: List[str]

# API端点
@router.get("/chatbots/")
def get_chatbots(db: Session = Depends(get_db)):
    """获取所有的聊天机器人配置"""
    return db.query(ChatBot).all()

@router.post("/chatbots/{client_id}/start")
def start_bot(client_id: str, db: Session = Depends(get_db)):
    """启动指定的聊天机器人"""
    bot = db.query(ChatBot).filter(ChatBot.client_id == client_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail=f"ChatBot with client_id {client_id} not found")
    
    success = process_manager.start_bot(
        client_id=bot.client_id,
        client_secret=bot.client_secret,
        url=DEFAULT_BOT_URL
    )
    
    if not success:
        # 可能已经在运行
        status = process_manager.get_status(client_id)
        if "error" in status:
            # 更新数据库中的状态为error
            bot.status = "error"
            db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to start bot: {status['error']}")
        # 如果机器人已经在运行，更新数据库中的状态
        bot.status = status["status"]
        db.commit()
        return status
    
    # 启动成功，更新数据库中的状态为running
    bot.status = "running"
    db.commit()
    return process_manager.get_status(client_id)

@router.post("/chatbots/{client_id}/stop")
def stop_bot(client_id: str, db: Session = Depends(get_db)):
    """停止指定的聊天机器人"""
    bot = db.query(ChatBot).filter(ChatBot.client_id == client_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail=f"ChatBot with client_id {client_id} not found")
        
    success = process_manager.stop_bot(client_id)
    if not success:
        # 更新状态为error
        bot.status = "error"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to stop bot {client_id}")
    
    # 更新数据库中的状态为stop
    bot.status = "stop"
    db.commit()
    return process_manager.get_status(client_id)

@router.post("/chatbots/{client_id}/restart")
def restart_bot(client_id: str, db: Session = Depends(get_db)):
    """重启指定的聊天机器人"""
    bot = db.query(ChatBot).filter(ChatBot.client_id == client_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail=f"ChatBot with client_id {client_id} not found")
    
    success = process_manager.restart_bot(client_id)
    if not success:
        # 尝试重新启动
        success = process_manager.start_bot(
            client_id=bot.client_id,
            client_secret=bot.client_secret,
            url=DEFAULT_BOT_URL
        )
        
        if not success:
            # 更新状态为error
            bot.status = "error"
            db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to restart bot {client_id}")
    
    # 更新数据库中的状态为running
    bot.status = "running"
    db.commit()
    return process_manager.get_status(client_id)

@router.get("/chatbots/{client_id}/status")
def get_bot_status(client_id: str, db: Session = Depends(get_db)):
    """获取指定聊天机器人的状态"""
    # 检查数据库中的机器人
    bot = db.query(ChatBot).filter(ChatBot.client_id == client_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail=f"ChatBot with client_id {client_id} not found")
        
    # 获取进程状态
    status = process_manager.get_status(client_id)
    if "error" in status:
        return {"client_id": client_id, "status": bot.status}
    
    # 如果进程状态与数据库状态不一致，则更新数据库
    if bot.status != status["status"]:
        bot.status = status["status"]
        db.commit()
    
    return status

@router.get("/chatbots/{client_id}/logs")
def get_bot_logs(client_id: str, max_lines: int = 100):
    """获取指定聊天机器人的日志"""
    logs = process_manager.get_bot_logs(client_id, max_lines)
    if "error" in logs:
        raise HTTPException(status_code=404, detail=logs["error"])
    
    return logs

@router.get("/chatbots/status")
def get_all_bots_status():
    """获取所有聊天机器人的状态"""
    return process_manager.get_status()

@router.post("/chatbots/start-all")
def start_all_bots(db: Session = Depends(get_db)):
    """启动所有聊天机器人"""
    bots = db.query(ChatBot).all()
    bot_list = [
        {
            "client_id": bot.client_id,
            "client_secret": bot.client_secret,
            "url": DEFAULT_BOT_URL
        }
        for bot in bots
    ]
    
    result = process_manager.start_all_bots(bot_list)
    
    # 更新所有机器人的状态到数据库
    for bot_result in result.get("results", []):
        client_id = bot_result.get("client_id")
        success = bot_result.get("success")
        status = "running" if success else "error"
        
        # 更新数据库状态
        bot = db.query(ChatBot).filter(ChatBot.client_id == client_id).first()
        if bot:
            bot.status = status
    
    db.commit()
    return result

@router.post("/chatbots/stop-all")
def stop_all_bots(db: Session = Depends(get_db)):
    """停止所有聊天机器人"""
    result = process_manager.stop_all_bots()
    
    # 更新所有机器人的状态为stop
    bots = db.query(ChatBot).all()
    for bot in bots:
        bot.status = "stop"
    
    db.commit()
    return result 