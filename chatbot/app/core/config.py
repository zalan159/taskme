from pathlib import Path
import yaml

# 项目基础路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"

# 加载配置文件
def load_config():
    config_path = CONFIG_DIR / "config.yml"
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

# 获取配置
config = load_config()

# API相关配置
api_config = config.get('api', {})
API_HOST = api_config.get('host', '0.0.0.0')
API_PORT = api_config.get('port', 8000)

# 数据库配置
db_config = config.get('mysql', {})
db_name = db_config.get('name', 'rag_flow')
db_user = db_config.get('user', 'root')
db_password = db_config.get('password', 'infini_rag_flow')
db_host = db_config.get('host', 'localhost')
db_port = db_config.get('port', 5455)

# 数据库URL配置
DATABASE_URL = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# 机器人配置
bot_config = config.get('bot', {})
DEFAULT_BOT_URL = bot_config.get('url', 'http://localhost:9380/v1/chatbot/chat')

# 日志配置
log_config = config.get('log', {})
LOG_LEVEL = log_config.get('level', 'INFO')
LOG_DIR = BASE_DIR / "logs"

# 确保日志目录存在
if not LOG_DIR.exists():
    LOG_DIR.mkdir(exist_ok=True)