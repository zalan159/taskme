#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
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

import io
import base64
from PIL import Image


def chunk(filename, binary, tenant_id, lang, callback=None, **kwargs):
    """
    简单处理图片，将图片转换为base64字符串并返回
    
    Args:
        filename: 文件名
        binary: 图片二进制数据
        tenant_id: 租户ID
        lang: 语言
        callback: 回调函数
        **kwargs: 其他参数
        
    Returns:
        包含图片信息的字典列表
    """
    # 打开图片并转换为RGB模式
    img = Image.open(io.BytesIO(binary)).convert('RGB')
    
    # 创建文档对象
    doc = {
        "docnm_kwd": filename,
        "image": img
    }
    
    # 如果有回调函数，更新进度
    if callback:
        callback(0.5, "图片已加载，准备转换为base64格式")
    
    # 将图片转换为base64字符串
    img_binary = io.BytesIO()
    img.save(img_binary, format='JPEG')
    img_binary.seek(0)
    img_base64 = base64.b64encode(img_binary.read()).decode('utf-8')
    
    # 更新文档对象，添加base64编码的图片
    doc["image_base64"] = img_base64
    
    # 如果有回调函数，更新进度
    if callback:
        callback(1.0, "图片已成功转换为base64格式")
    
    return [doc] 