# 🚀 全局入口：启动 FastAPI 实例，挂载所有的 API 路由，配置跨域(CORS)和全局异常处理。
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.v1 import auth, chat, llm_settings, memory, profile, retrieve
from services.session import auto_flush_background_task

# 配置日志（必须在 logger 使用前）
logging.basicConfig(
    level=logging.INFO,  # 生产环境设为 INFO，调试时改为 DEBUG
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# 全局后台任务引用
_background_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理"""
    global _background_task

    # Startup: 重置并预热 LLM 单例
    from services.llm.factory import LLMFactory
    LLMFactory.reset()

    logger.info("预热 LLM 客户端...")
    llm = LLMFactory.get_provider()
    logger.info("LLM 客户端已初始化")

    # 预热：发送一个简单请求建立连接
    async def warmup_llm():
        try:
            await llm.generate_chat_response(
                system_prompt="You are an assistant",
                context="",
                user_query="OK",
            )
            logger.info("LLM 连接预热完成")
        except Exception as e:
            logger.warning(f"LLM 预热失败（不影响服务）: {e}")

    # 后台执行预热，不阻塞启动
    asyncio.create_task(warmup_llm())

    # Startup: 启动后台任务
    logger.info("启动自动落库后台任务")
    _background_task = asyncio.create_task(auto_flush_background_task())

    yield

    # Shutdown: 取消后台任务
    if _background_task:
        logger.info("取消自动落库后台任务")
        _background_task.cancel()
        try:
            await _background_task
        except asyncio.CancelledError:
            pass


# 创建 FastAPI 实例
app = FastAPI(
    title="Mymem API",
    description="双轨记忆系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应该限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(llm_settings.router)
app.include_router(memory.router)
app.include_router(profile.router)
app.include_router(retrieve.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# 挂载前端静态文件（必须放在最后）
from pathlib import Path
frontend_path = Path(__file__).parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
