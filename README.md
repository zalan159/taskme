<div align="center">
<a href="https://oa.frontfidelity.cn:9222/">
<img src="web/public/logo.svg" width="350" alt="ragflow logo">
</a>
</div>


## 💡 TaskMe(Ragflow_Agent_Enhance) 是什么？

本项目TaskMe探长智能体基于 [RAGFlow](https://ragflow.io/) v0.17 分支开发，是一款专注于知识库和智能Agent的开源RAG（Retrieval-Augmented Generation）引擎。在此，我们向RAGFlow原始团队表示诚挚的感谢，感谢他们为开源社区贡献了如此优秀的基础架构。同时我们提供了不开源的企业级TaskMe用户端，可以将后台编辑的Agent发布为：
1. 移动端
2. PC端
让RAGFlow不止作为探索研究性的项目，更能成为企业级的应用，赋能更多员工。


### 🎯 项目理念

我们认为RAGFlow的知识库功能非常强大，但原有的chat功能相对简单，而Agent功能还有很大的提升空间。因此，我们做出了以下改进：

- **精简功能模块**：移除了传统的chat对话功能，避免功能冗余
- **增强Agent能力**：大幅扩展和优化了Agent功能，使其成为核心特色
- **双核心架构**：将系统重新设计为**知识库**和**智能Agent**两大核心功能模块

这样的设计让用户可以更专注于构建强大的知识库系统和智能化的Agent应用，为企业级AI应用提供更精准的解决方案。

RAGFlow 可以为各种规模的企业及个人提供一套精简的 RAG 工作流程，结合大语言模型（LLM）针对用户各类不同的复杂格式数据提供可靠的问答以及有理有据的引用。

## 🎮 Demo 试用

请登录网址 [https://oa.frontfidelity.cn:9222](https://oa.frontfidelity.cn:9222) 试用 后台编辑器demo。

TaskMe用户端demo：
[https://oa.frontfidelity.cn:8099](https://oa.frontfidelity.cn:8099)



## 🚀 Agent功能增强

基于RAGFlow v0.17，我们对Agent功能进行了大幅度增强和优化：

### 🤖 核心Agent能力
- **MCP组件集成**：完成MCP（Model Context Protocol）组件的引用功能，支持更灵活的模型交互
- **照片描述组件**：新增图像理解能力，支持上传图片并生成智能描述
- **语音转文字**：集成用户语音转文字功能，提升交互体验
- **微信端支持**：添加微信端token支持和微信登录注册功能

### 🛠️ Agent管理优化
- **权限管理**：细化Agent团队权限操作，增加标签和权限功能
- **钉钉聊天机器人绑定**：支持Agent绑定钉钉聊天机器人，扩展应用场景
- **最近使用记录**：新增获取最近使用的Agent接口
- **用户体验**：前端增加编辑Agent信息入口，优化Agent运行界面

### 🔧 技术架构改进
- **Gunicorn部署优化**：改进项目启动方式，从传统方式迁移到Gunicorn，提升服务器性能和稳定性
- **流式处理优化**：优化MCP流式处理和引用处理机制
- **缓存机制**：优化工具缓存机制，提升性能表现
- **历史消息处理**：增强输入获取的错误处理和输出合并逻辑
- **提示词处理**：增强MCP客户端的提示词处理功能，支持正则表达式匹配

### 🌐 集成能力扩展
- **后台机器人调度**：增加后台机器人调度服务器
- **工单系统**：添加工单系统服务选项，支持企业级应用
- **多模态支持**：在Agent聊天中支持图像、语音、文本等多种输入模态



## 🌟 主要功能

### 📚 **强大的知识库系统**

#### 🍭 **"Quality in, quality out"**

- 基于[深度文档理解](./deepdoc/README.md)，能够从各类复杂格式的非结构化数据中提取真知灼见。
- 真正在无限上下文（token）的场景下快速完成大海捞针测试。

#### 🍱 **基于模板的文本切片**

- 不仅仅是智能，更重要的是可控可解释。
- 多种文本模板可供选择

#### 🌱 **有理有据、最大程度降低幻觉（hallucination）**

- 文本切片过程可视化，支持手动调整。
- 有理有据：答案提供关键引用的快照并支持追根溯源。

#### 🍔 **兼容各类异构数据源**

- 支持丰富的文件类型，包括 Word 文档、PPT、excel 表格、txt 文件、图片、PDF、影印件、复印件、结构化数据、网页等。

### 🤖 **智能Agent系统**

#### 🧠 **多模态交互能力**

- 支持文本、图片、语音等多种输入方式
- 集成MCP（Model Context Protocol）组件，实现灵活的模型交互
- 照片描述功能，为图像提供智能化分析

#### 🔧 **灵活的Agent管理**

- 细粒度的权限管理和团队协作
- 支持Agent标签分类和快速检索
- 聊天机器人绑定，扩展应用场景

#### 🌐 **企业级集成**

- 微信端支持，无缝集成移动端应用
- 工单系统集成，支持企业级业务流程
- 后台机器人调度，实现自动化任务处理

### 🛀 **全程无忧、自动化的 RAG 工作流**

- 全面优化的 RAG 工作流可以支持从个人应用乃至超大型企业的各类生态系统。
- 大语言模型 LLM 以及向量模型均支持配置。
- 基于多路召回、融合重排序。
- 提供易用的 API，可以轻松集成到各类企业系统。

## 🔎 系统架构

<div align="center" style="margin-top:20px;margin-bottom:20px;">
<img src="https://github.com/infiniflow/ragflow/assets/12318111/d6ac5664-c237-4200-a7c2-a4a00691b485" width="1000"/>
</div>

## 🎬 快速开始

### 📝 前提条件

- CPU >= 4 核
- RAM >= 16 GB
- Disk >= 50 GB
- Docker >= 24.0.0 & Docker Compose >= v2.26.1
  > 如果你并没有在本机安装 Docker（Windows、Mac，或者 Linux）, 可以参考文档 [Install Docker Engine](https://docs.docker.com/engine/install/) 自行安装。

### 🚀 启动服务器

1. 确保 `vm.max_map_count` 不小于 262144：

   > 如需确认 `vm.max_map_count` 的大小：
   >
   > ```bash
   > $ sysctl vm.max_map_count
   > ```
   >
   > 如果 `vm.max_map_count` 的值小于 262144，可以进行重置：
   >
   > ```bash
   > # 这里我们设为 262144:
   > $ sudo sysctl -w vm.max_map_count=262144
   > ```
   >
   > 你的改动会在下次系统重启时被重置。如果希望做永久改动，还需要在 **/etc/sysctl.conf** 文件里把 `vm.max_map_count` 的值再相应更新一遍：
   >
   > ```bash
   > vm.max_map_count=262144
   > ```

2. 克隆仓库：

   ```bash
   $ git clone https://github.com/zalan159/taskme.git
   ```

3. 进入 **docker** 文件夹，利用提前编译好的 Docker 镜像启动服务器：

> [!CAUTION]
> 请注意，目前官方提供的所有 Docker 镜像均基于 x86 架构构建，并不提供基于 ARM64 的 Docker 镜像。
> 如果你的操作系统是 ARM64 架构，请参考[这篇文档](https://ragflow.io/docs/dev/build_docker_image)自行构建 Docker 镜像。

   > 运行以下命令会自动下载 RAGFlow slim Docker 镜像 `v0.17.0-slim`。请参考下表查看不同 Docker 发行版的描述。如需下载不同于 `v0.17.0-slim` 的 Docker 镜像，请在运行 `docker compose` 启动服务之前先更新 **docker/.env** 文件内的 `RAGFLOW_IMAGE` 变量。比如，你可以通过设置 `RAGFLOW_IMAGE=infiniflow/ragflow:v0.17.0` 来下载 RAGFlow 镜像的 `v0.17.0` 完整发行版。

   ```bash
   $ cd ragflow/docker
   $ docker compose -f docker-compose.yml up -d
   ```

4. **配置必要的配置文件**：

   在启动服务之前，你需要根据示例文件创建相应的配置文件：

   ```bash
   # 复制并配置chatbot配置文件
   $ cp chatbot/config/config.yml.example chatbot/config/config.yml
   # 编辑配置文件，填入你的MySQL连接信息和RAGFlow服务地址
   
   # 复制并配置web前端配置文件
   $ cp web/src/conf.json.example web/src/conf.json
   # 编辑配置文件，填入你的应用名称和微信配置信息
   
   # 复制测试数据文件（如果需要运行SDK测试）
   $ cp sdk/python/test/test_sdk_api/test_data/test.json.example sdk/python/test/test_sdk_api/test_data/test.json
   ```

   **配置文件说明**：
   
   - **chatbot/config/config.yml**: Chatbot服务配置
     - `mysql`: 数据库连接配置（主机、端口、用户名、密码）
     - `api`: API服务配置（主机和端口）
     - `bot`: RAGFlow聊天机器人URL配置
     - `log`: 日志级别配置

   - **web/src/conf.json**: Web前端配置
     - `appName`: 应用显示名称
     - `industryOptions`: 行业选项配置
     - `wechat`: 微信登录配置（AppID和回调URI）

   - **sdk/python/test/test_sdk_api/test_data/test.json**: SDK测试数据
     - 包含实体名称和别名的测试数据，用于SDK功能测试

   | RAGFlow image tag | Image size (GB) | Has embedding models? | Stable?                  |
   | ----------------- | --------------- | --------------------- | ------------------------ |
   | v0.17.0           | &approx;9       | :heavy_check_mark:    | Stable release           |
   | v0.17.0-slim      | &approx;2       | ❌                    | Stable release           |
   | nightly           | &approx;9       | :heavy_check_mark:    | _Unstable_ nightly build |
   | nightly-slim      | &approx;2       | ❌                     | _Unstable_ nightly build |

   > [!TIP]
   > 如果你遇到 Docker 镜像拉不下来的问题，可以在 **docker/.env** 文件内根据变量 `RAGFLOW_IMAGE` 的注释提示选择华为云或者阿里云的相应镜像。
   >
   > - 华为云镜像名：`swr.cn-north-4.myhuaweicloud.com/infiniflow/ragflow`
   > - 阿里云镜像名：`registry.cn-hangzhou.aliyuncs.com/infiniflow/ragflow`

4. 服务器启动成功后再次确认服务器状态：

   ```bash
   $ docker logs -f ragflow-server
   ```

   _出现以下界面提示说明服务器启动成功：_

   ```bash
        ____   ___    ______ ______ __
       / __ \ /   |  / ____// ____// /____  _      __
      / /_/ // /| | / / __ / /_   / // __ \| | /| / /
     / _, _// ___ |/ /_/ // __/  / // /_/ /| |/ |/ /
    /_/ |_|/_/  |_|\____//_/    /_/ \____/ |__/|__/

    * Running on all addresses (0.0.0.0)
   ```

   > 如果您在没有看到上面的提示信息出来之前，就尝试登录 RAGFlow，你的浏览器有可能会提示 `network anormal` 或 `网络异常`。

5. 在你的浏览器中输入你的服务器对应的 IP 地址并登录 RAGFlow。
   > 上面这个例子中，您只需输入 http://IP_OF_YOUR_MACHINE 即可：未改动过配置则无需输入端口（默认的 HTTP 服务端口 80）。
6. 在 [service_conf.yaml.template](./docker/service_conf.yaml.template) 文件的 `user_default_llm` 栏配置 LLM factory，并在 `API_KEY` 栏填写和你选择的大模型相对应的 API key。

   > 详见 [llm_api_key_setup](https://ragflow.io/docs/dev/llm_api_key_setup)。

   _好戏开始，接着奏乐接着舞！_

## 🔧 系统配置

系统配置涉及以下三份文件：

- [.env](./docker/.env)：存放一些基本的系统环境变量，比如 `SVR_HTTP_PORT`、`MYSQL_PASSWORD`、`MINIO_PASSWORD` 等。
- [service_conf.yaml.template](./docker/service_conf.yaml.template)：配置各类后台服务。
- [docker-compose.yml](./docker/docker-compose.yml): 系统依赖该文件完成启动。

请务必确保 [.env](./docker/.env) 文件中的变量设置与 [service_conf.yaml.template](./docker/service_conf.yaml.template) 文件中的配置保持一致！

如果不能访问镜像站点 hub.docker.com 或者模型站点 huggingface.co，请按照 [.env](./docker/.env) 注释修改 `RAGFLOW_IMAGE` 和 `HF_ENDPOINT`。

> [./docker/README](./docker/README.md) 解释了 [service_conf.yaml.template](./docker/service_conf.yaml.template) 用到的环境变量设置和服务配置。

如需更新默认的 HTTP 服务端口(80), 可以在 [docker-compose.yml](./docker/docker-compose.yml) 文件中将配置 `80:80` 改为 `<YOUR_SERVING_PORT>:80`。

> 所有系统配置都需要通过系统重启生效：
>
> ```bash
> $ docker compose -f docker-compose.yml up -d
> ```

### 把文档引擎从 Elasticsearch 切换成为 Infinity

RAGFlow 默认使用 Elasticsearch 存储文本和向量数据. 如果要切换为 [Infinity](https://github.com/infiniflow/infinity/), 可以按照下面步骤进行:

1. 停止所有容器运行:

   ```bash
   $ docker compose -f docker/docker-compose.yml down -v
   ```
   Note: `-v` 将会删除 docker 容器的 volumes，已有的数据会被清空。

2. 设置 **docker/.env** 目录中的 `DOC_ENGINE` 为 `infinity`.

3. 启动容器:

   ```bash
   $ docker compose -f docker-compose.yml up -d
   ```

> [!WARNING]
> Infinity 目前官方并未正式支持在 Linux/arm64 架构下的机器上运行.

## 🔧 源码编译 Docker 镜像（不含 embedding 模型）

本 Docker 镜像大小约 2 GB 左右并且依赖外部的大模型和 embedding 服务。

```bash
git clone https://github.com/infiniflow/ragflow.git
cd ragflow/
docker build --build-arg LIGHTEN=1 --build-arg NEED_MIRROR=1 -f Dockerfile -t infiniflow/ragflow:nightly-slim .
```

## 🔧 源码编译 Docker 镜像（包含 embedding 模型）

本 Docker 大小约 9 GB 左右。由于已包含 embedding 模型，所以只需依赖外部的大模型服务即可。

```bash
git clone https://github.com/infiniflow/ragflow.git
cd ragflow/
docker build --build-arg NEED_MIRROR=1 -f Dockerfile -t infiniflow/ragflow:nightly .
```

## 🔨 以源代码启动服务

1. 安装 uv。如已经安装，可跳过本步骤：

   ```bash
   pipx install uv
   export UV_INDEX=https://mirrors.aliyun.com/pypi/simple
   ```

2. 下载源代码并安装 Python 依赖：

   ```bash
   git clone https://github.com/infiniflow/ragflow.git
   cd ragflow/
   uv sync --python 3.10 --all-extras # install RAGFlow dependent python modules
   ```

3. 通过 Docker Compose 启动依赖的服务（MinIO, Elasticsearch, Redis, and MySQL）：

   ```bash
   docker compose -f docker/docker-compose-base.yml up -d
   ```

   在 `/etc/hosts` 中添加以下代码，将 **conf/service_conf.yaml** 文件中的所有 host 地址都解析为 `127.0.0.1`：

   ```
   127.0.0.1       es01 infinity mysql minio redis
   ```

4. 如果无法访问 HuggingFace，可以把环境变量 `HF_ENDPOINT` 设成相应的镜像站点：

   ```bash
   export HF_ENDPOINT=https://hf-mirror.com
   ```

5. 启动后端服务：

   ```bash
   source .venv/bin/activate
   export PYTHONPATH=$(pwd)
   bash docker/launch_backend_service.sh
   ```

6. 安装前端依赖：
   ```bash
   cd web
   npm install
   ```
7. 启动前端服务：

   ```bash
   npm run dev
   ```

   _以下界面说明系统已经成功启动：_

   ![](https://github.com/user-attachments/assets/0daf462c-a24d-4496-a66f-92533534e187)

## 🤝 商务合作


## 👥 加入社区

