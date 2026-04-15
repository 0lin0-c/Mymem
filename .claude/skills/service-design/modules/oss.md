# OSS 模块

本文档定义对象存储服务的设计规范。

---

## 1. OSS 客户端接口

```python
class BaseOSSClient(ABC):
    """对象存储客户端基类"""

    @abstractmethod
    async def upload(
        self,
        file_content: bytes,
        filename: str,
        modality: str,
        user_id: str,
    ) -> str:
        """上传文件，返回存储路径"""
        pass

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """下载文件"""
        pass

    @abstractmethod
    async def get_url(self, path: str, expire_seconds: int = 3600) -> str:
        """获取临时访问 URL"""
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """删除文件"""
        pass
```

---

## 2. 存储路径命名规范

**格式**：`{user_id}/{modality}/{yyyy-mm-dd}/{uuid}.{ext}`

**示例**：
```
a1b2c3d4-e5f6-7890-abcd-ef1234567890/
├── text/
│   └── 2024-03-20/
│       └── 550e8400-e29b-41d4-a716-446655440000.json
├── image/
│   └── 2024-03-21/
│       └── 660f9511-f39c-52e5-b827-557766551111.png
└── voice/
    └── 2024-03-22/
        └── 770fa622-g40d-63f6-c938-668877662222.mp3
```

**设计意图**：
- 按 `user_id` 隔离：便于用户数据导出/删除（GDPR 合规）
- 按 `modality` 分类：便于存储审计和容量统计
- 按 `yyyy-mm-dd` 分区：便于数据清洗和冷热分离

---

## 3. 实现状态

| 客户端 | 说明 | 状态 |
|--------|------|------|
| `LocalOSSClient` | 本地文件存储（开发用） | ✅ 已实现 |
| `AliyunOSSClient` | 阿里云 OSS | ✅ 已实现 |
