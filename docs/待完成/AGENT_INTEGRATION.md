# 🦾 Agent 能力扩展方案：让记忆系统"动手操作"

## 1. 背景与目标

当前 Mymem 项目是一个**纯粹的记记系统**：存储记忆、检索记忆、构建上下文。但它缺乏**行动能力**——无法操作电脑、执行任务、与外部世界交互。

本方案参考 OpenClaw 等项目，为记忆系统"装上手脚"，使其进化为**具备行动能力的智能 Agent**。

### 目标架构

```
┌──────────────────────────────────────────────────────────────┐
│                     Mymem Agent System                       │
├──────────────────────────────────────────────────────────────┤
│  用户请求                                                     │
│      │                                                        │
│      ▼                                                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │ Memory Layer│ ←→ │ Agent Core  │ ←→ │ Tool Layer  │      │
│  │ (已有)      │    │ (新增)      │    │ (新增)      │      │
│  │ - 检索记忆  │    │ - 规划      │    │ - 文件操作  │      │
│  │ - 存储记忆  │    │ - 执行      │    │ - 网页浏览  │      │
│  │ - 构建上下文│    │ - 反思      │    │ - 代码执行  │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│                            │                                 │
│                            ▼                                 │
│                     ┌─────────────┐                         │
│                     │ Memory Store│ ← 行动结果自动存储       │
│                     └─────────────┘                         │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. 核心概念：Memory + Tool = Agent

### 2.1 为什么需要记忆？

传统的 Agent（如 AutoGPT、BabyAGI）缺乏长期记忆：
- 上下文窗口有限，无法记住所有历史
- 跨会话无法保持连贯性
- 无法从过往经验中学习

**Mymem 的优势**：
- 长期记忆存储
- 语义检索能力
- 用户画像和偏好

### 2.2 Agent 架构设计

```
┌────────────────────────────────────────────────────────────┐
│                    Agent 执行循环                          │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  1. 感知 (Perception)                                      │
│     └─ 从记忆中检索相关上下文                              │
│                                                            │
│  2. 规划 (Planning)                                        │
│     └─ LLM 根据上下文 + 用户请求，生成行动计划             │
│                                                            │
│  3. 执行 (Action)                                          │
│     └─ 调用工具执行操作                                    │
│                                                            │
│  4. 反思 (Reflection)                                      │
│     └─ 评估执行结果，更新记忆                              │
│                                                            │
│  5. 学习 (Learning)                                        │
│     └─ 将行动结果存入记忆系统                              │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 3. 工具层设计（Tool Layer）

### 3.1 工具分类

| 类别 | 工具 | 功能 | 优先级 |
|------|------|------|--------|
| **文件操作** | `file_read` | 读取文件内容 | P0 |
| | `file_write` | 写入文件 | P0 |
| | `file_delete` | 删除文件 | P1 |
| | `directory_list` | 列出目录内容 | P0 |
| **代码执行** | `python_exec` | 执行 Python 代码 | P0 |
| | `bash_exec` | 执行 Shell 命令 | P1 |
| **网络操作** | `web_search` | 网络搜索 | P1 |
| | `web_fetch` | 获取网页内容 | P1 |
| **系统操作** | `process_list` | 列出进程 | P2 |
| | `process_kill` | 终止进程 | P2 |

### 3.2 工具接口定义

```python
# services/tools/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum


class ToolCategory(Enum):
    FILE = "file"
    CODE = "code"
    NETWORK = "network"
    SYSTEM = "system"


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = None


class BaseTool(ABC):
    """工具基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（供 LLM 理解）"""
        pass

    @property
    @abstractmethod
    def category(self) -> ToolCategory:
        """工具类别"""
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """参数 JSON Schema"""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具"""
        pass

    def to_openai_tool(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            }
        }
```

### 3.3 文件操作工具实现

```python
# services/tools/file_tools.py
import os
import aiofiles
from pathlib import Path
from typing import Optional

from services.tools.base import BaseTool, ToolResult, ToolCategory


class FileReadTool(BaseTool):
    """文件读取工具"""

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "读取指定路径的文件内容"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径"
                },
                "encoding": {
                    "type": "string",
                    "default": "utf-8",
                    "description": "文件编码"
                }
            },
            "required": ["path"]
        }

    async def execute(self, path: str, encoding: str = "utf-8") -> ToolResult:
        try:
            # 安全检查：防止路径遍历攻击
            safe_path = Path(path).resolve()

            if not safe_path.exists():
                return ToolResult(success=False, output=None, error=f"文件不存在: {path}")

            if not safe_path.is_file():
                return ToolResult(success=False, output=None, error=f"路径不是文件: {path}")

            async with aiofiles.open(safe_path, 'r', encoding=encoding) as f:
                content = await f.read()

            return ToolResult(
                success=True,
                output=content,
                metadata={"path": str(safe_path), "size": len(content)}
            )

        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class FileWriteTool(BaseTool):
    """文件写入工具"""

    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return "将内容写入指定路径的文件"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要写入的文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容"
                },
                "mode": {
                    "type": "string",
                    "enum": ["write", "append"],
                    "default": "write",
                    "description": "写入模式：write(覆盖) 或 append(追加)"
                }
            },
            "required": ["path", "content"]
        }

    async def execute(
        self,
        path: str,
        content: str,
        mode: str = "write"
    ) -> ToolResult:
        try:
            safe_path = Path(path).resolve()

            # 确保父目录存在
            safe_path.parent.mkdir(parents=True, exist_ok=True)

            write_mode = 'w' if mode == "write" else 'a'

            async with aiofiles.open(safe_path, write_mode, encoding='utf-8') as f:
                await f.write(content)

            return ToolResult(
                success=True,
                output=f"成功写入 {len(content)} 字符到 {path}",
                metadata={"path": str(safe_path), "size": len(content)}
            )

        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class DirectoryListTool(BaseTool):
    """目录列表工具"""

    @property
    def name(self) -> str:
        return "directory_list"

    @property
    def description(self) -> str:
        return "列出指定目录下的文件和子目录"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要列出的目录路径，默认为当前目录"
                },
                "pattern": {
                    "type": "string",
                    "description": "文件名匹配模式（支持通配符）"
                }
            }
        }

    async def execute(
        self,
        path: str = ".",
        pattern: str = "*"
    ) -> ToolResult:
        try:
            safe_path = Path(path).resolve()

            if not safe_path.exists():
                return ToolResult(success=False, output=None, error=f"目录不存在: {path}")

            if not safe_path.is_dir():
                return ToolResult(success=False, output=None, error=f"路径不是目录: {path}")

            items = list(safe_path.glob(pattern))

            result = []
            for item in items:
                result.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                    "modified": item.stat().st_mtime,
                })

            return ToolResult(
                success=True,
                output=result,
                metadata={"path": str(safe_path), "count": len(result)}
            )

        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
```

### 3.4 代码执行工具

```python
# services/tools/code_tools.py
import subprocess
import tempfile
import os
from typing import Optional

from services.tools.base import BaseTool, ToolResult, ToolCategory


class PythonExecTool(BaseTool):
    """Python 代码执行工具"""

    @property
    def name(self) -> str:
        return "python_exec"

    @property
    def description(self) -> str:
        return "执行 Python 代码并返回结果"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CODE

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码"
                },
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "description": "执行超时时间（秒）"
                }
            },
            "required": ["code"]
        }

    async def execute(
        self,
        code: str,
        timeout: int = 30
    ) -> ToolResult:
        try:
            # 在临时文件中执行，避免污染环境
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False
            ) as f:
                f.write(code)
                temp_path = f.name

            try:
                result = subprocess.run(
                    ['python', temp_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                output = result.stdout
                error = result.stderr if result.returncode != 0 else None

                return ToolResult(
                    success=result.returncode == 0,
                    output=output,
                    error=error,
                    metadata={"return_code": result.returncode}
                )

            finally:
                os.unlink(temp_path)

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output=None,
                error=f"执行超时（{timeout}秒）"
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
```

---

## 4. Agent 核心设计（Agent Core）

### 4.1 Agent 控制循环

```python
# services/agent/core.py
import asyncio
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from services.llm.base import BaseLLMProvider
from services.retrieval.retriever import MemoryRetriever
from services.memory.writer import MemoryWriter
from services.tools.base import BaseTool, ToolResult


class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"


@dataclass
class AgentStep:
    """Agent 执行步骤"""
    thought: str           # LLM 的思考过程
    tool_name: str         # 选择的工具
    tool_args: dict        # 工具参数
    result: Optional[ToolResult] = None


@dataclass
class AgentSession:
    """Agent 会话"""
    user_id: str
    original_request: str
    steps: List[AgentStep] = field(default_factory=list)
    final_answer: Optional[str] = None
    success: bool = False


class AgentCore:
    """Agent 核心：规划-执行-反思循环"""

    SYSTEM_PROMPT = """你是一个具备行动能力的智能助手。
你可以使用工具来完成任务，同时拥有长期记忆能力。

# 可用工具
{tools_description}

# 记忆上下文
{memory_context}

# 工作流程
1. 思考：分析任务，决定下一步行动
2. 行动：选择工具并执行
3. 观察：评估执行结果
4. 重复以上步骤直到完成任务

# 输出格式
每次回复必须使用 JSON 格式：
{{
    "thought": "你的思考过程",
    "action": "工具名称或 'finish'",
    "action_input": {{工具参数}} 或 {{"answer": "最终答案"}},
    "need_memory": true/false  // 是否需要记住这次交互
}}
"""

    def __init__(
        self,
        llm: BaseLLMProvider,
        retriever: MemoryRetriever,
        writer: MemoryWriter,
        tools: List[BaseTool],
        max_steps: int = 10,
    ):
        self.llm = llm
        self.retriever = retriever
        self.writer = writer
        self.tools = {tool.name: tool for tool in tools}
        self.max_steps = max_steps

    def _build_tools_description(self) -> str:
        """构建工具描述"""
        descriptions = []
        for tool in self.tools.values():
            desc = f"- {tool.name}: {tool.description}\n"
            desc += f"  参数: {json.dumps(tool.parameters_schema, ensure_ascii=False)}"
            descriptions.append(desc)
        return "\n".join(descriptions)

    async def execute(self, user_id: str, request: str) -> AgentSession:
        """执行 Agent 任务"""
        session = AgentSession(
            user_id=user_id,
            original_request=request,
        )

        # 1. 从记忆中检索相关上下文
        memory_context = await self.retriever.build_context(
            user_id=user_id,
            query=request,
            max_tokens=1000,
        )

        # 2. 构建系统提示
        system_prompt = self.SYSTEM_PROMPT.format(
            tools_description=self._build_tools_description(),
            memory_context=memory_context or "暂无相关记忆",
        )

        # 3. 执行循环
        messages = [{"role": "user", "content": request}]

        for step_num in range(self.max_steps):
            # 调用 LLM
            response = await self.llm.generate_chat_response(
                system_prompt=system_prompt,
                context="",
                user_query="\n".join([m["content"] for m in messages[-3:]]),
            )

            # 解析响应
            try:
                action_data = json.loads(response)
            except json.JSONDecodeError:
                # 尝试提取 JSON
                action_data = self._extract_json(response)

            step = AgentStep(
                thought=action_data.get("thought", ""),
                tool_name=action_data.get("action", "finish"),
                tool_args=action_data.get("action_input", {}),
            )

            # 检查是否完成
            if step.tool_name == "finish":
                session.final_answer = step.tool_args.get("answer", "")
                session.success = True
                break

            # 执行工具
            tool = self.tools.get(step.tool_name)
            if tool:
                step.result = await tool.execute(**step.tool_args)

                # 将结果加入消息
                messages.append({
                    "role": "assistant",
                    "content": json.dumps({
                        "thought": step.thought,
                        "action": step.tool_name,
                        "result": step.result.output if step.result.success else step.result.error,
                    }, ensure_ascii=False)
                })
            else:
                messages.append({
                    "role": "assistant",
                    "content": f"错误：未知工具 {step.tool_name}"
                })

            session.steps.append(step)

        # 4. 存储执行结果到记忆
        if session.success and session.steps:
            await self._save_to_memory(session)

        return session

    async def _save_to_memory(self, session: AgentSession) -> None:
        """将 Agent 执行过程存入记忆"""
        # 构建执行摘要
        actions_summary = "\n".join([
            f"- {step.tool_name}: {step.result.output if step.result else 'N/A'}"
            for step in session.steps
        ])

        memory_content = f"""任务: {session.original_request}
执行步骤:
{actions_summary}
结果: {session.final_answer}"""

        await self.writer.save_chat(
            user_id=session.user_id,
            user_input=session.original_request,
            assistant_response=memory_content,
            modality="text",
        )

    def _extract_json(self, text: str) -> dict:
        """从文本中提取 JSON"""
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group())
        return {"action": "finish", "action_input": {"answer": text}}
```

### 4.2 工具注册表

```python
# services/tools/registry.py
from typing import List, Type

from services.tools.base import BaseTool
from services.tools.file_tools import FileReadTool, FileWriteTool, DirectoryListTool
from services.tools.code_tools import PythonExecTool


class ToolRegistry:
    """工具注册表"""

    _tools: dict[str, Type[BaseTool]] = {}

    @classmethod
    def register(cls, tool_class: Type[BaseTool]) -> None:
        """注册工具"""
        instance = tool_class()
        cls._tools[instance.name] = tool_class

    @classmethod
    def get_tool(cls, name: str) -> BaseTool:
        """获取工具实例"""
        tool_class = cls._tools.get(name)
        return tool_class() if tool_class else None

    @classmethod
    def get_all_tools(cls) -> List[BaseTool]:
        """获取所有工具实例"""
        return [tool_class() for tool_class in cls._tools.values()]

    @classmethod
    def get_openai_tools(cls) -> List[dict]:
        """获取 OpenAI Function Calling 格式的工具列表"""
        return [tool.to_openai_tool() for tool in cls.get_all_tools()]


# 注册默认工具
ToolRegistry.register(FileReadTool)
ToolRegistry.register(FileWriteTool)
ToolRegistry.register(DirectoryListTool)
ToolRegistry.register(PythonExecTool)
```

---

## 5. 与现有系统集成

### 5.1 目录结构扩展

```
Mymem/
├── services/
│   ├── agent/                 # 新增：Agent 核心
│   │   ├── __init__.py
│   │   ├── core.py            # AgentCore
│   │   └── state.py           # AgentSession, AgentStep
│   │
│   ├── tools/                 # 新增：工具层
│   │   ├── __init__.py
│   │   ├── base.py            # BaseTool, ToolResult
│   │   ├── registry.py        # ToolRegistry
│   │   ├── file_tools.py      # 文件操作工具
│   │   ├── code_tools.py      # 代码执行工具
│   │   ├── web_tools.py       # 网络操作工具
│   │   └── system_tools.py    # 系统操作工具
│   │
│   ├── llm/                   # 已有：LLM 服务
│   ├── memory/                # 已有：记忆服务
│   ├── retrieval/             # 已有：检索服务
│   └── session/               # 已有：会话服务
│
├── api/v1/
│   └── agent.py               # 新增：Agent API 路由
│
└── schemas/
    └── agent_schema.py        # 新增：Agent 请求/响应模型
```

### 5.2 API 设计

```python
# api/v1/agent.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_llm
from schemas.agent_schema import AgentRequest, AgentResponse
from services.agent.core import AgentCore
from services.retrieval.retriever import MemoryRetriever
from services.memory.writer import MemoryWriter
from services.tools.registry import ToolRegistry

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/execute", response_model=AgentResponse)
async def execute_agent(
    request: AgentRequest,
    db: AsyncSession = Depends(get_db),
    llm = Depends(get_llm),
):
    """执行 Agent 任务"""
    retriever = MemoryRetriever(db, llm)
    writer = MemoryWriter(db, llm)
    tools = ToolRegistry.get_all_tools()

    agent = AgentCore(
        llm=llm,
        retriever=retriever,
        writer=writer,
        tools=tools,
        max_steps=request.max_steps,
    )

    session = await agent.execute(
        user_id=request.user_id,
        request=request.task,
    )

    return AgentResponse(
        success=session.success,
        answer=session.final_answer,
        steps=[
            {
                "thought": step.thought,
                "tool": step.tool_name,
                "result": step.result.output if step.result else None,
            }
            for step in session.steps
        ],
    )
```

### 5.3 Schema 定义

```python
# schemas/agent_schema.py
from pydantic import BaseModel
from typing import List, Optional, Any


class AgentRequest(BaseModel):
    """Agent 执行请求"""
    user_id: str
    task: str
    max_steps: int = 10


class AgentStepResponse(BaseModel):
    """Agent 步骤响应"""
    thought: str
    tool: str
    result: Any


class AgentResponse(BaseModel):
    """Agent 执行响应"""
    success: bool
    answer: Optional[str]
    steps: List[AgentStepResponse]
```

---

## 6. 安全设计

### 6.1 沙箱隔离

```python
# services/tools/sandbox.py
import os
from pathlib import Path

class SandboxConfig:
    """沙箱配置"""

    # 允许访问的根目录
    ALLOWED_ROOTS = [
        os.path.expanduser("~/workspace"),
        os.path.expanduser("~/documents"),
    ]

    # 禁止访问的路径
    FORBIDDEN_PATHS = [
        "/etc/passwd",
        "/etc/shadow",
        os.path.expanduser("~/.ssh"),
        os.path.expanduser("~/.env"),
    ]

    # 允许执行的命令白名单
    ALLOWED_COMMANDS = [
        "python",
        "pip",
        "git",
    ]


def validate_path(path: str) -> bool:
    """验证路径是否在允许范围内"""
    resolved = Path(path).resolve()

    # 检查是否在允许的根目录下
    for root in SandboxConfig.ALLOWED_ROOTS:
        if str(resolved).startswith(str(Path(root).resolve())):
            return True

    # 检查是否在禁止列表中
    for forbidden in SandboxConfig.FORBIDDEN_PATHS:
        if str(resolved).startswith(forbidden):
            return False

    return False


def validate_command(command: str) -> bool:
    """验证命令是否允许执行"""
    base_cmd = command.split()[0] if command else ""
    return base_cmd in SandboxConfig.ALLOWED_COMMANDS
```

### 6.2 权限控制

```python
# services/tools/permission.py
from enum import Enum
from typing import Set

class Permission(Enum):
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    CODE_EXEC = "code_exec"
    NETWORK = "network"


class PermissionManager:
    """权限管理器"""

    def __init__(self, user_permissions: Set[Permission]):
        self.permissions = user_permissions

    def check(self, required: Permission) -> bool:
        """检查是否有指定权限"""
        return required in self.permissions

    def require(self, required: Permission) -> None:
        """要求权限，无权限则抛出异常"""
        if not self.check(required):
            raise PermissionError(f"缺少权限: {required.value}")
```

---

## 7. 实现步骤

### Phase 1：工具层基础（2-3 天）

1. [ ] 创建 `services/tools/` 目录
2. [ ] 实现 `BaseTool` 抽象基类
3. [ ] 实现 `FileReadTool`、`FileWriteTool`、`DirectoryListTool`
4. [ ] 实现 `ToolRegistry` 注册表
5. [ ] 编写单元测试

### Phase 2：Agent 核心（3-4 天）

1. [ ] 创建 `services/agent/` 目录
2. [ ] 实现 `AgentCore` 控制循环
3. [ ] 实现记忆集成（检索上下文、存储结果）
4. [ ] 实现安全沙箱
5. [ ] 编写集成测试

### Phase 3：API 与集成（2-3 天）

1. [ ] 实现 Agent API 路由
2. [ ] 实现 Schema 定义
3. [ ] 与现有 Chat API 集成
4. [ ] 前端交互界面（可选）

### Phase 4：扩展工具（持续）

1. [ ] 网络操作工具（`web_search`, `web_fetch`）
2. [ ] 系统操作工具（`process_list`, `process_kill`）
3. [ ] 数据库操作工具
4. [ ] 自定义工具扩展机制

---

## 8. 使用示例

### 8.1 基础使用

```python
# 示例：让 Agent 整理文件
from services.agent.core import AgentCore
from services.tools.registry import ToolRegistry

agent = AgentCore(
    llm=llm_provider,
    retriever=retriever,
    writer=writer,
    tools=ToolRegistry.get_all_tools(),
)

session = await agent.execute(
    user_id="user-123",
    request="帮我读取 ~/workspace/notes 目录下的所有 markdown 文件，并生成一个目录索引",
)

print(session.final_answer)
```

### 8.2 API 调用

```bash
curl -X POST http://localhost:8000/v1/agent/execute \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "task": "帮我分析当前项目的代码结构",
    "max_steps": 10
  }'
```

---

## 9. 后续扩展

| 方向 | 说明 |
|------|------|
| **多 Agent 协作** | 多个 Agent 分工合作完成任务 |
| **工具学习** | Agent 自动学习新工具的使用方法 |
| **人机协作** | 关键决策点请求人类确认 |
| **记忆驱动规划** | 从历史记忆中学习最优策略 |
| **可视化调试** | Agent 执行流程的可视化展示 |

---

## 10. 参考项目

| 项目 | 借鉴点 |
|------|--------|
| OpenClaw | 工具调用机制、沙箱设计 |
| AutoGPT | Agent 循环架构 |
| LangChain | Tool 抽象设计 |
| BabyAGI | 任务规划与执行分离 |
