# core/config.py
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """应用全局配置"""

    # 1. 数据库配置 (从 .env 中读取 DATABASE_URL)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mymem"

    # 2. LLM 大模型配置
    llm_provider: str = "openai"  # openai | anthropic | openai-compatible

    # OpenAI 及兼容模型配置（对话）
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None  # 国内模型需要配置各自的 base_url
    chat_model: str = "gpt-4o-mini"  # 对话模型名称
    openai_proxy: Optional[str] = None  # 代理地址，设为空字符串 "" 表示禁用代理，None 表示使用系统代理

    # 向量模型配置
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536  # 向量维度（根据 embedding 模型调整）
    embedding_api_key: Optional[str] = None  # 向量模型的 API Key（可选，默认复用 openai_api_key）
    embedding_base_url: Optional[str] = None  # 向量模型的 URL（可选，默认复用 openai_base_url）

    # Anthropic 配置
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: Optional[str] = None  # 自定义 Anthropic 端点

    # 3. JWT 鉴权配置 (未来做前端登录用)
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # 4. Agent 记忆策略配置
    forgetting_threshold: int = 30  # 遗忘系数（天）
    max_category_summary_length: int = 2000

    # 5. OSS 存储配置
    oss_provider: str = "local"  # local | aliyun | s3
    # 阿里云 OSS 配置
    aliyun_oss_access_key_id: Optional[str] = None
    aliyun_oss_access_key_secret: Optional[str] = None
    aliyun_oss_endpoint: Optional[str] = None  # 如 oss-cn-hangzhou.aliyuncs.com
    aliyun_oss_bucket_name: Optional[str] = None

    # 6. Redis 配置（分布式 Session）
    redis_url: Optional[str] = None  # 如 redis://localhost:6379/0

    # 7. 多模态处理配置
    # VLM 配置（用于图片/视频理解）
    vlm_model: str = "gpt-4o"  # 或 gpt-4-vision-preview, qwen-vl-plus 等
    # ASR 配置（语音转文字）
    asr_provider: str = "openai"  # openai | aliyun | azure
    aliyun_asr_app_key: Optional[str] = None
    aliyun_asr_access_key_id: Optional[str] = None
    aliyun_asr_access_key_secret: Optional[str] = None

    # 🚀 V2 版本的核心魔法在这里：
    # 告诉 Pydantic 去读取 .env 文件，如果 .env 里有一些这里没定义的变量，直接 allow (允许/忽略)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False # 忽略大小写，.env写 DATABASE_URL，这里写 database_url 也能自动匹配上
    )

# 实例化单例，全局只在启动时读取一次
settings = Settings()