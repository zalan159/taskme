import asyncio
import pandas as pd
from agent.component.mcpclient import MCP, MCPParam, MCPServerConfig

class MockCanvas:
    def __init__(self):
        self.components = {}
        self.history = []
        self.tenant_id = "test_tenant"
        
    def get_component(self, component_id):
        return self.components.get(component_id, {})
        
    def get_history(self, limit=1):
        return self.history[-limit:]
        
    def get_tenant_id(self):
        return self.tenant_id
        
    def get_embedding_model(self):
        return "test_embedding_model"

def test_mcp_run():
    # 创建模拟的 canvas
    canvas = MockCanvas()
    
    # 创建 MCP 参数
    mcp_param = MCPParam("test_mcp")
    mcp_param.prompt = "你是一个有帮助的AI助手。"
    
    # 配置服务器
    server_config = MCPServerConfig(
        url="https://api.deepseek.com/v1",
        headers={"Authorization": "Bearer test-token"},
        timeout=30,
        sse_read_timeout=300
    )
    mcp_param.set_server(server_config)
    
    # 创建 MCP 组件
    mcp = MCP(canvas, "test_mcp_id", mcp_param)
    
    # 准备测试数据
    history = [
        ["user", "你好，请介绍一下你自己"],
        ["assistant", "你好！我是一个AI助手，很高兴为你服务。"],
        ["user", "你能做什么？"]
    ]
    
    # 运行测试
    try:
        result = mcp._run(history)
        print("测试结果:")
        print(result)
        
        # 验证结果
        if isinstance(result, pd.DataFrame):
            print("\n结果类型正确: DataFrame")
            print("结果内容:", result["content"].iloc[0])
        else:
            print("\n结果类型:", type(result))
            
    except Exception as e:
        print("测试过程中发生错误:", str(e))
        import traceback
        print("错误堆栈:", traceback.format_exc())

if __name__ == "__main__":
    test_mcp_run() 