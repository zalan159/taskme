# 使用Python 3.9作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 创建必要的目录
RUN mkdir -p /app/config /app/logs

# 复制项目文件
COPY requirements.txt .
COPY app ./app
COPY main.py .
COPY config/config.yml ./config/

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口（FastAPI默认端口为8000）
EXPOSE 8000

# 启动应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
