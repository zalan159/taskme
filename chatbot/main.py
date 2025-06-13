from fastapi import FastAPI
from app.api.endpoints import router
from app.core.process_manager import process_manager
from app.core.config import API_HOST, API_PORT, DEFAULT_BOT_URL
from app.db.database import SessionLocal, engine, Base
from app.db.models import ChatBot
from contextlib import asynccontextmanager

import uvicorn
import atexit
import logging

# 配置全局日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log")
    ]
)

logger = logging.getLogger(__name__)

# 使用新的lifespan上下文管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    logger.info("钉钉机器人管理系统启动")
    
    # 创建数据库表（如果不存在）
    Base.metadata.create_all(bind=engine)
    
    # 启动所有配置的机器人
    logger.info("正在启动所有配置的机器人...")
    try:
        db = SessionLocal()
        bots = db.query(ChatBot).all()
        
        if not bots:
            logger.warning("未找到任何机器人配置")
        else:
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
            logger.info(f"机器人启动结果: {result}")
    except Exception as e:
        logger.error(f"启动机器人时出错: {e}")
    finally:
        db.close()
    
    yield  # 这里是应用正常运行的阶段
    
    # 关闭时执行
    logger.info("应用关闭，停止所有机器人进程")
    try:
        db = SessionLocal()
        process_manager.stop_all_bots()
        
        # 更新所有机器人状态为stop
        bots = db.query(ChatBot).all()
        for bot in bots:
            bot.status = "stop"
        
        db.commit()
    except Exception as e:
        logger.error(f"停止机器人时出错: {e}")
    finally:
        if 'db' in locals():
            db.close()

# 创建FastAPI应用
app = FastAPI(
    title="钉钉机器人管理系统",
    description="管理多个钉钉机器人进程的API",
    version="0.0.1",
    lifespan=lifespan
)

# 注册路由
app.include_router(router)

# 也使用atexit确保即使在意外情况下也能正确清理
atexit.register(process_manager.stop_all_bots)

if __name__ == "__main__":
    logger.info(f"启动服务器，监听 {API_HOST}:{API_PORT}")
    uvicorn.run(app, host=API_HOST, port=API_PORT)