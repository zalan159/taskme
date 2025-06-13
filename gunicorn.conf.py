import multiprocessing
import yaml
import os

# # Read configuration from service_conf.yaml
# config_path = os.path.join(os.path.dirname(__file__), 'conf', 'service_conf.yaml')
# with open(config_path, 'r') as f:
#     config = yaml.safe_load(f)

# # Get port from config, default to 9380 if not found
# port = config.get('service', {}).get('port', 9380)

port = 9380

# Gunicorn configuration
bind = f"0.0.0.0:{port}"
workers = 2  # 减少worker数量
worker_class = "sync"
timeout = 120
keepalive = 5  # 减少keepalive超时
worker_connections = 100  # 降低连接数

# 禁用预加载以避免数据库连接共享问题
preload_app = False

# Server socket
backlog = 2048

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = "info"

# Process naming
proc_name = "ragflow"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL
keyfile = None
certfile = None

def post_fork(server, worker):
    from api.db.db_models import DB
    try:
        DB.connect(reuse_if_open=True)
        worker.log.info("Database connection established in worker process.")
    except Exception as e:
        worker.log.error(f"Failed to connect to database in worker process: {e}")

# 进程退出前关闭数据库连接
def worker_exit(server, worker):
    from api.db.db_models import DB, close_connection
    try:
        close_connection()
        if hasattr(DB, 'close_all'):
            DB.close_all()
    except:
        pass 