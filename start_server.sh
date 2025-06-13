#!/bin/bash

# 激活虚拟环境
source .venv/bin/activate

# 设置 PYTHONPATH
export PYTHONPATH=$(pwd)

# 启动后端服务
bash docker/launch_backend_service.sh
# gunicorn -c gunicorn.conf.py "api.ragflow_server:create_app()"
