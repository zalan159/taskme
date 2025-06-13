# 钉钉机器人管理系统

这是一个用于管理多个钉钉机器人进程的FastAPI应用。可以从数据库中获取机器人配置，并管理每个机器人进程的启动、停止和监控。

## 项目结构

```
project/
├── app/                        # 应用模块
│   ├── api/                    # API相关模块
│   │   ├── endpoints.py        # API端点定义
│   │   └── __init__.py
│   ├── core/                   # 核心功能模块
│   │   ├── config.py           # 应用配置
│   │   ├── process_manager.py  # 进程管理器
│   │   └── __init__.py
│   ├── db/                     # 数据库相关模块
│   │   ├── database.py         # 数据库连接
│   │   ├── models.py           # 数据模型
│   │   └── __init__.py
│   ├── bots/                   # 机器人脚本
│   │   ├── test_openkag.py     # 钉钉机器人脚本
│   │   └── __init__.py
│   └── __init__.py
├── logs/                       # 日志目录
├── main.py                     # 入口文件
├── requirements.txt            # 依赖项
├── Dockerfile                  # Docker构建文件
├── docker-compose.yml          # Docker Compose配置
└── README.md                   # 项目文档
```

## 依赖项

- Python 3.8+
- FastAPI
- SQLAlchemy
- dingtalk-stream
- psutil
- PyMySQL

## 安装

### 方法一：直接安装

1. 克隆仓库
2. 安装依赖：

```bash
pip install -r requirements.txt
```

### 方法二：使用Docker

```bash
# 使用Docker Compose构建和启动服务
docker-compose up -d
```

## 环境变量

可通过环境变量配置应用参数:

- `API_HOST`: API服务器主机 (默认: "0.0.0.0")
- `API_PORT`: API服务器端口 (默认: 18000)
- `DATABASE_URL`: 数据库连接URL
- `DEFAULT_BOT_URL`: 钉钉机器人API地址

## 数据库设置

数据库模型定义在`app/db/models.py`中，确保您的数据库包含正确的模式。ChatBot表需要包括以下字段：

- client_id: 主键，钉钉机器人的应用ID
- client_secret: 钉钉机器人的应用密钥
- user_id: 用户ID
- canvas_id: 画布ID

## 运行

启动FastAPI服务：

```bash
python main.py
```

默认情况下，服务将在端口18000上运行。

## API 文档

启动服务后，访问 http://localhost:18000/docs 查看自动生成的API文档。

主要端点：

- `GET /chatbots/` - 获取所有机器人配置
- `POST /chatbots/{client_id}/start` - 启动指定机器人
- `POST /chatbots/{client_id}/stop` - 停止指定机器人
- `POST /chatbots/{client_id}/restart` - 重启指定机器人
- `GET /chatbots/{client_id}/status` - 获取指定机器人状态
- `GET /chatbots/{client_id}/logs` - 获取指定机器人日志
- `GET /chatbots/status` - 获取所有机器人状态
- `POST /chatbots/start-all` - 启动所有机器人
- `POST /chatbots/stop-all` - 停止所有机器人

## 机器人进程

每个机器人进程运行`app/bots/test_openkag.py`脚本，该脚本负责与钉钉Stream API连接并处理消息。进程管理器会监控每个进程的状态，并在需要时启动或停止它们。

所有机器人日志都会被保存在`logs/{client_id}/`目录中，便于排查问题。

## 示例使用

启动所有机器人：

```bash
curl -X POST http://localhost:18000/chatbots/start-all
```

检查特定机器人状态：

```bash
curl -X GET http://localhost:18000/chatbots/{client_id}/status
```

停止所有机器人：

```bash
curl -X POST http://localhost:18000/chatbots/stop-all
``` 