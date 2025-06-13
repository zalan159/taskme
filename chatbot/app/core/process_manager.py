import subprocess
import psutil
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
import pathlib

# 设置日志记录到文件
log_dir = pathlib.Path("logs")
if not log_dir.exists():
    log_dir.mkdir(exist_ok=True)

# 配置logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# 同时输出到控制台和文件
file_handler = logging.FileHandler(log_dir / "process_manager.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

@dataclass
class BotProcess:
    client_id: str
    process: subprocess.Popen
    client_secret: str
    url: str
    status: str = "running"

class ProcessManager:
    def __init__(self):
        self.processes: Dict[str, BotProcess] = {}
        
    def start_bot(self, client_id: str, client_secret: str, url: str) -> bool:
        """启动一个机器人进程"""
        if client_id in self.processes and self.processes[client_id].status == "running":
            # 检查进程是否仍在运行
            if self.processes[client_id].process.poll() is None:
                logger.info(f"Bot {client_id} is already running")
                return False
            else:
                # 进程已经结束，但状态仍为running，更新状态
                self.processes[client_id].status = "stop"
        
        # 创建日志目录
        log_path = log_dir / client_id
        if not log_path.exists():
            log_path.mkdir(exist_ok=True)
            
        # 启动新进程
        try:
            # 更新路径为新的目录结构
            cmd = [
                "python3", "-m", "app.bots.test_openkag",
                "--client_id", client_id,
                "--client_secret", client_secret,
                "--url", url
            ]
            
            # 创建日志文件
            stdout_log = open(log_path / "stdout.log", "a")
            stderr_log = open(log_path / "stderr.log", "a")
            
            process = subprocess.Popen(
                cmd,
                stdout=stdout_log,
                stderr=stderr_log,
                text=True
            )
            
            self.processes[client_id] = BotProcess(
                client_id=client_id,
                process=process,
                client_secret=client_secret,
                url=url
            )
            
            logger.info(f"Started bot {client_id} with PID {process.pid}")
            return True
        except Exception as e:
            logger.error(f"Failed to start bot {client_id}: {str(e)}")
            return False
    
    def stop_bot(self, client_id: str) -> bool:
        """停止一个机器人进程"""
        if client_id not in self.processes:
            logger.warning(f"Bot {client_id} is not managed by this process manager")
            return False
            
        bot_process = self.processes[client_id]
        if bot_process.status == "stop":
            logger.info(f"Bot {client_id} is already stopped")
            return True
            
        try:
            # 尝试正常终止进程
            if bot_process.process.poll() is None:  # 检查进程是否仍在运行
                # 在Linux/Mac上，尝试发送SIGTERM信号
                try:
                    parent = psutil.Process(bot_process.process.pid)
                    for child in parent.children(recursive=True):
                        child.terminate()
                    parent.terminate()
                    parent.wait(timeout=3)  # 等待进程终止
                except psutil.NoSuchProcess:
                    pass  # 进程可能已经终止
                except Exception as e:
                    logger.error(f"Error terminating process: {str(e)}")
                    # 如果无法正常终止，尝试强制终止
                    bot_process.process.kill()
            
            bot_process.status = "stop"
            logger.info(f"Stopped bot {client_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop bot {client_id}: {str(e)}")
            bot_process.status = "error"
            return False
    
    def restart_bot(self, client_id: str) -> bool:
        """重启一个机器人进程"""
        if client_id not in self.processes:
            logger.warning(f"Bot {client_id} is not managed by this process manager")
            return False
            
        bot_process = self.processes[client_id]
        
        # 停止现有进程
        self.stop_bot(client_id)
        
        # 启动新进程
        return self.start_bot(
            client_id=bot_process.client_id,
            client_secret=bot_process.client_secret,
            url=bot_process.url
        )
    
    def get_status(self, client_id: str = None) -> Dict:
        """获取所有或指定机器人的状态"""
        if client_id:
            if client_id not in self.processes:
                return {"error": f"Bot {client_id} not found"}
                
            bot_process = self.processes[client_id]
            # 检查进程是否仍在运行
            is_running = bot_process.process.poll() is None
            status = "running" if is_running else "stop"
            
            # 更新状态
            if bot_process.status != status:
                bot_process.status = status
                
            return {
                "client_id": client_id,
                "status": bot_process.status,
                "pid": bot_process.process.pid if is_running else None,
                "code": 0
            }
        else:
            result = []
            for cid, bot_process in self.processes.items():
                is_running = bot_process.process.poll() is None
                status = "running" if is_running else "stop"
                
                # 更新状态
                if bot_process.status != status:
                    bot_process.status = status
                    
                result.append({
                    "client_id": cid,
                    "status": bot_process.status,
                    "pid": bot_process.process.pid if is_running else None
                })
            return {"bots": result}
    
    def get_bot_logs(self, client_id: str, max_lines: int = 100) -> Dict:
        """获取指定机器人的日志"""
        if client_id not in self.processes:
            return {"error": f"Bot {client_id} not found"}
            
        log_path = log_dir / client_id
        
        try:
            # 从日志文件读取而不是从进程输出中读取
            stdout_lines = []
            stderr_lines = []
            
            # 读取stdout日志
            stdout_log_path = log_path / "stdout.log"
            if stdout_log_path.exists():
                with open(stdout_log_path, "r") as f:
                    stdout_lines = f.readlines()[-max_lines:] if max_lines > 0 else f.readlines()
                    stdout_lines = [line.strip() for line in stdout_lines]
            
            # 读取stderr日志
            stderr_log_path = log_path / "stderr.log"
            if stderr_log_path.exists():
                with open(stderr_log_path, "r") as f:
                    stderr_lines = f.readlines()[-max_lines:] if max_lines > 0 else f.readlines()
                    stderr_lines = [line.strip() for line in stderr_lines]
            
            return {
                "client_id": client_id,
                "stdout": stdout_lines,
                "stderr": stderr_lines
            }
        except Exception as e:
            return {"error": f"Failed to get logs for bot {client_id}: {str(e)}"}
    
    def start_all_bots(self, bots: List[Dict]) -> Dict:
        """启动所有配置的机器人"""
        results = []
        for bot in bots:
            client_id = bot.get("client_id")
            client_secret = bot.get("client_secret")
            url = bot.get("url", "http://localhost:9222/v1/chatbot/chat")
            
            success = self.start_bot(
                client_id=client_id,
                client_secret=client_secret,
                url=url
            )
            
            results.append({
                "client_id": client_id,
                "success": success,
                "status": self.get_status(client_id) if success else {"error": "Failed to start"}
            })
            
        return {"results": results}
    
    def stop_all_bots(self) -> Dict:
        """停止所有机器人"""
        results = []
        for client_id in list(self.processes.keys()):
            success = self.stop_bot(client_id)
            results.append({
                "client_id": client_id,
                "success": success
            })
            
        return {"results": results}

# 创建一个全局进程管理器实例
process_manager = ProcessManager() 