#!/bin/bash

# 创建目标目录
mkdir -p ../ragflow-mcpclient

# 读取 changed_files.txt 并复制文件
cat changed_files.txt | while read file; do
  mkdir -p "../ragflow-mcpclient/$(dirname "$file")"
  cp "$file" "../ragflow-mcpclient/$file"
done
