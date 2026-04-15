# LLM 设置表单设计

## 1. 表单字段

| 字段 | 前端 ID | 类型 | 必填 | 说明 |
|------|---------|------|------|------|
| LLM 提供商 | `llm_provider` | select | 是 | openai/deepseek/qwen/glm/anthropic/custom |
| API Base URL | `llm_base_url` | text | 否 | 自定义 API 地址 |
| API Key | `llm_api_key` | password | 是 | 用户的 API Key |
| 模型名称 | `llm_model` | text | 是 | 如 gpt-4o、deepseek-chat |

## 2. 提供商默认值

当用户选择不同提供商时，自动填充提示：

| 提供商 | 默认 Base URL | 常用模型 |
|--------|---------------|----------|
| openai | https://api.openai.com/v1 | gpt-4o, gpt-3.5-turbo |
| deepseek | https://api.deepseek.com/v1 | deepseek-chat |
| qwen | https://dashscope.aliyuncs.com/compatible-mode/v1 | qwen-plus, qwen-turbo |
| glm | https://open.bigmodel.cn/api/paas/v4 | glm-4 |
| anthropic | （无） | claude-sonnet-4-20250514 |
| custom | （用户输入） | （用户输入） |

## 3. 保存流程

```
用户点击"保存并预热"
      ↓
前端校验：API Key 和模型名称必填
      ↓
POST /v1/user/llm-settings
      ↓
显示"正在预热 LLM 连接..."
      ↓
轮询 GET /v1/user/llm-settings/{user_id}
      ↓
warmed_up = true → 显示成功，跳转聊天页
```

## 4. API 请求格式

### 保存配置

```
PUT /v1/user/llm-settings
{
    "user_id": "xxx",
    "llm_provider": "deepseek",
    "llm_api_key": "sk-xxx",
    "llm_base_url": "https://api.deepseek.com/v1",
    "llm_model": "deepseek-chat"
}
```

### 获取状态

```
GET /v1/user/llm-settings/{user_id}

Response:
{
    "configured": true,
    "llm_provider": "deepseek",
    "llm_base_url": "https://api.deepseek.com/v1",
    "llm_model": "deepseek-chat",
    "warmed_up": true
}
```

## 5. 错误处理

| 场景 | 处理方式 |
|------|----------|
| API Key 为空 | 前端校验拦截 |
| 预热超时 | 30秒后提示"预热超时，请检查配置" |
| API Key 无效 | 预热失败，显示错误信息 |
