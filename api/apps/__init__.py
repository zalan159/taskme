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
import os
import sys
import logging
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from flask import Blueprint, Flask, jsonify
from werkzeug.wrappers.request import Request
from flask_cors import CORS
from flasgger import Swagger
from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer

from api.db import StatusEnum
from api.db.db_models import close_connection, DB
from api.db.services import UserService
from api.utils import CustomJSONEncoder, commands

from flask_session import Session
from flask_login import LoginManager
from api import settings
from api.utils.api_utils import server_error_response
from api.constants import API_VERSION

# Get a logger instance for this module
logger = logging.getLogger(__name__)

__all__ = ["app"]

Request.json = property(lambda self: self.get_json(force=True, silent=True))

app = Flask(__name__)

@app.before_request
def _db_connect():
    try:
        if DB.is_closed():
            DB.connect()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

# Add this at the beginning of your file to configure Swagger UI
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,  # Include all endpoints
            "model_filter": lambda tag: True,  # Include all models
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}

swagger = Swagger(
    app,
    config=swagger_config,
    template={
        "swagger": "2.0",
        "info": {
            "title": "RAGFlow API",
            "description": "",
            "version": "1.0.0",
        },
        "securityDefinitions": {
            "ApiKeyAuth": {"type": "apiKey", "name": "Authorization", "in": "header"}
        },
    },
)

CORS(app, 
     supports_credentials=True, 
     max_age=2592000,
     resources={r"/*": {
         "origins": ["http://localhost:8000", "http://127.0.0.1:9380", "http://localhost:9380"],
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
         "expose_headers": ["Content-Type", "Authorization"],
     }})
app.url_map.strict_slashes = False
app.json_encoder = CustomJSONEncoder
app.errorhandler(Exception)(server_error_response)

## convince for dev and debug
# app.config["LOGIN_DISABLED"] = True
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("MAX_CONTENT_LENGTH", 128 * 1024 * 1024)
)

Session(app)
login_manager = LoginManager()
login_manager.init_app(app)

commands.register_commands(app)


def search_pages_path(pages_dir):
    app_path_list = [
        path for path in pages_dir.glob("*_app.py") if not path.name.startswith(".")
    ]
    api_path_list = [
        path for path in pages_dir.glob("*sdk/*.py") if not path.name.startswith(".")
    ]
    app_path_list.extend(api_path_list)
    return app_path_list


def register_page(page_path):
    path = f"{page_path}"

    page_name = page_path.stem.rstrip("_app")
    module_name = ".".join(
        page_path.parts[page_path.parts.index("api"): -1] + (page_name,)
    )

    spec = spec_from_file_location(module_name, page_path)
    page = module_from_spec(spec)
    page.app = app
    page.manager = Blueprint(page_name, module_name)
    sys.modules[module_name] = page
    spec.loader.exec_module(page)
    page_name = getattr(page, "page_name", page_name)
    sdk_path = "\\sdk\\" if sys.platform.startswith("win") else "/sdk/"
    url_prefix = (
        f"/api/{API_VERSION}" if sdk_path in path else f"/{API_VERSION}/{page_name}"
    )

    app.register_blueprint(page.manager, url_prefix=url_prefix)
    return url_prefix


pages_dir = [
    Path(__file__).parent,
    Path(__file__).parent.parent / "api" / "apps",
    Path(__file__).parent.parent / "api" / "apps" / "sdk",
]

client_urls_prefix = [
    register_page(path) for dir in pages_dir for path in search_pages_path(dir)
]

logger.info(f"Registered voice blueprint with prefix: /api/{API_VERSION}/voice")

@login_manager.request_loader
def load_user(web_request):
    jwt = Serializer(secret_key=settings.SECRET_KEY)
    authorization = web_request.headers.get("Authorization")
    # logging.info(f"[Auth Debug] Authorization header: {authorization}")
    if authorization:
        try:
            # 处理可能的多重Bearer前缀问题
            if authorization.startswith("Bearer "):
                # 提取token部分
                parts = authorization.split()
                if len(parts) >= 2:
                    # 如果有多个Bearer前缀，只保留最后一个token部分
                    access_token = parts[-1]
                    # logging.info(f"[Auth Debug] Extracted token: {access_token}")
                    
                    # 查询用户
                    user = UserService.query(
                        access_token=access_token, status=StatusEnum.VALID.value
                    )
                    if user:
                        # logging.info(f"[Auth Debug] Found user with direct token: {user}")
                        return user[0]
                    else:
                        logging.warning(f"[Auth Debug] No user found with token: {access_token}")
            
            # 如果上面的方法失败，尝试解码 token
            try:
                access_token = str(jwt.loads(authorization))
                # logging.info(f"[Auth Debug] First decode attempt: {access_token}")
                
                # 检查是否是双重编码的 token
                if access_token.startswith('"') and access_token.endswith('"'):
                    # 去掉引号，获取实际的 access_token
                    actual_token = access_token[1:-1]
                    logging.info(f"[Auth Debug] Detected double-encoded token, actual token: {actual_token}")
                    user = UserService.query(
                        access_token=actual_token, status=StatusEnum.VALID.value
                    )
                else:
                    # 直接使用解码后的 token
                    user = UserService.query(
                        access_token=access_token, status=StatusEnum.VALID.value
                    )
            except Exception as first_decode_error:
                # logging.warning(f"[Auth Debug] First decode attempt failed: {first_decode_error}")
                # 尝试双重解码
                try:
                    # 先解码一次
                    intermediate_token = str(jwt.loads(authorization))
                    # logging.info(f"[Auth Debug] Intermediate token: {intermediate_token}")
                    # 再解码一次
                    access_token = str(jwt.loads(intermediate_token))
                    # logging.info(f"[Auth Debug] Second decode attempt: {access_token}")
                    user = UserService.query(
                        access_token=access_token, status=StatusEnum.VALID.value
                    )
                except Exception as second_decode_error:
                    # logging.warning(f"[Auth Debug] Second decode attempt failed: {second_decode_error}")
                    return None
                
            # logging.info(f"[Auth Debug] Found user: {user}")
            if user:
                return user[0]
            else:
                # logging.warning("[Auth Debug] No user found with the given access token")
                return None
        except Exception as e:
            # logging.warning(f"[Auth Debug] load_user got exception {e}")
            return None
    else:
        # logging.warning("[Auth Debug] No Authorization header found")
        return None


@app.teardown_request
def _db_close(exc):
    if not DB.is_closed():
        DB.close()

# Add health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"}), 200
