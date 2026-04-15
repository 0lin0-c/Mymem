# ☁️ OSS 存储测试：本地存储 + 阿里云 OSS
import os
import pytest
import tempfile
import shutil
from pathlib import Path

from services.oss.local_client import LocalOSSClient
from services.oss.base import BaseOSSClient


class TestLocalOSSClient:
    """LocalOSSClient 本地存储测试"""

    @pytest.fixture
    def temp_storage(self):
        """创建临时存储目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def local_client(self, temp_storage):
        """创建本地存储客户端"""
        return LocalOSSClient(base_path=temp_storage)

    @pytest.mark.asyncio
    async def test_upload_file(self, local_client, test_user):
        """测试上传文件"""
        content = b"Hello, this is test content"
        path = await local_client.upload(
            file_content=content,
            filename="test.txt",
            modality="document",
            user_id=test_user.id,
        )

        assert path is not None
        assert test_user.id in path
        assert "document" in path

    @pytest.mark.asyncio
    async def test_upload_image(self, local_client, test_user):
        """测试上传图片"""
        # 模拟图片数据
        content = b"\x89PNG\r\n\x1a\n" + b"fake image data"
        path = await local_client.upload(
            file_content=content,
            filename="test.png",
            modality="image",
            user_id=test_user.id,
        )

        assert "image" in path
        assert ".png" in path

    @pytest.mark.asyncio
    async def test_download_file(self, local_client, test_user):
        """测试下载文件"""
        content = b"Test content for download"
        path = await local_client.upload(
            file_content=content,
            filename="download_test.txt",
            modality="document",
            user_id=test_user.id,
        )

        downloaded = await local_client.download(path)

        assert downloaded == content

    @pytest.mark.asyncio
    async def test_download_nonexistent_file(self, local_client):
        """测试下载不存在的文件"""
        with pytest.raises(FileNotFoundError):
            await local_client.download("non/existent/path.txt")

    @pytest.mark.asyncio
    async def test_get_url(self, local_client, test_user):
        """测试获取文件 URL"""
        content = b"Test content"
        path = await local_client.upload(
            file_content=content,
            filename="url_test.txt",
            modality="document",
            user_id=test_user.id,
        )

        url = await local_client.get_url(path)

        # 本地存储返回绝对路径
        assert url is not None
        assert os.path.exists(url) or Path(url).exists()

    @pytest.mark.asyncio
    async def test_delete_file(self, local_client, test_user):
        """测试删除文件"""
        content = b"Content to delete"
        path = await local_client.upload(
            file_content=content,
            filename="delete_test.txt",
            modality="document",
            user_id=test_user.id,
        )

        deleted = await local_client.delete(path)
        assert deleted is True

        # 再次删除应该返回 False
        deleted_again = await local_client.delete(path)
        assert deleted_again is False

    @pytest.mark.asyncio
    async def test_upload_requires_user_id(self, local_client):
        """测试上传需要 user_id"""
        with pytest.raises(ValueError, match="user_id"):
            await local_client.upload(
                file_content=b"test",
                filename="test.txt",
                modality="document",
                user_id="",  # 空 user_id
            )

    @pytest.mark.asyncio
    async def test_path_generation(self, local_client, test_user):
        """测试路径生成格式"""
        content = b"Test"
        path = await local_client.upload(
            file_content=content,
            filename="test.txt",
            modality="image",
            user_id=test_user.id,
        )

        # 路径格式: {user_id}/{modality}/{YYYY-MM-DD}/{uuid}.{ext}
        parts = path.split("/")
        assert parts[0] == test_user.id
        assert parts[1] == "image"
        assert parts[2].count("-") == 2  # 日期格式 YYYY-MM-DD

    @pytest.mark.asyncio
    async def test_directories_created(self, temp_storage):
        """测试存储目录自动创建"""
        client = LocalOSSClient(base_path=temp_storage)

        # 检查模态子目录是否创建
        for modality in ["image", "video", "voice", "document"]:
            modality_path = Path(temp_storage) / modality
            assert modality_path.exists()

    @pytest.mark.asyncio
    async def test_different_modalities(self, local_client, test_user):
        """测试不同模态存储"""
        modalities = ["image", "video", "voice", "document"]
        paths = []

        for modality in modalities:
            path = await local_client.upload(
                file_content=b"test",
                filename=f"test_{modality}.bin",
                modality=modality,
                user_id=test_user.id,
            )
            paths.append(path)
            assert modality in path

        # 每个模态的路径应该不同
        assert len(set(paths)) == len(modalities)


class TestAliyunOSSClient:
    """AliyunOSSClient 阿里云 OSS 测试"""

    def test_initialization_missing_config(self):
        """测试缺少配置时初始化失败"""
        with pytest.raises(ValueError, match="配置不完整"):
            from services.oss.aliyun_client import AliyunOSSClient
            AliyunOSSClient(
                access_key_id="",
                access_key_secret="",
                endpoint="",
                bucket_name="",
            )

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skip(reason="需要真实的阿里云 OSS 配置")
    async def test_upload_to_oss(self):
        """测试上传到阿里云 OSS（需要配置）"""
        # 需要配置真实的环境变量才能运行
        pass

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skip(reason="需要真实的阿里云 OSS 配置")
    async def test_download_from_oss(self):
        """测试从阿里云 OSS 下载"""
        pass

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skip(reason="需要真实的阿里云 OSS 配置")
    async def test_get_signed_url(self):
        """测试获取签名 URL"""
        pass


class TestOSSClientInterface:
    """OSS 客户端接口测试"""

    def test_local_client_implements_interface(self):
        """测试 LocalOSSClient 实现了接口"""
        client = LocalOSSClient.__new__(LocalOSSClient)
        assert isinstance(client, BaseOSSClient)

        # 检查必需方法存在
        assert hasattr(client, 'upload')
        assert hasattr(client, 'download')
        assert hasattr(client, 'get_url')
        assert hasattr(client, 'delete')


class TestOSSFileOperations:
    """OSS 文件操作集成测试"""

    @pytest.fixture
    def temp_storage(self):
        """创建临时存储目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_upload_download_cycle(self, temp_storage, test_user):
        """测试上传下载完整周期"""
        client = LocalOSSClient(base_path=temp_storage)

        original_content = b"Original content for cycle test"
        path = await client.upload(
            file_content=original_content,
            filename="cycle_test.txt",
            modality="document",
            user_id=test_user.id,
        )

        downloaded = await client.download(path)
        assert downloaded == original_content

    @pytest.mark.asyncio
    async def test_overwrite_file(self, temp_storage, test_user):
        """测试文件覆盖（不同内容同名上传）"""
        client = LocalOSSClient(base_path=temp_storage)

        # 第一次上传
        await client.upload(
            file_content=b"First content",
            filename="test.txt",
            modality="document",
            user_id=test_user.id,
        )

        # 第二次上传（会生成不同文件名，所以不会覆盖）
        path2 = await client.upload(
            file_content=b"Second content",
            filename="test.txt",
            modality="document",
            user_id=test_user.id,
        )

        # 两个文件都应该存在
        downloaded = await client.download(path2)
        assert downloaded == b"Second content"

    @pytest.mark.asyncio
    async def test_large_file_upload(self, temp_storage, test_user):
        """测试大文件上传"""
        client = LocalOSSClient(base_path=temp_storage)

        # 创建 1MB 的测试文件
        large_content = b"x" * (1024 * 1024)
        path = await client.upload(
            file_content=large_content,
            filename="large_test.bin",
            modality="document",
            user_id=test_user.id,
        )

        downloaded = await client.download(path)
        assert len(downloaded) == len(large_content)

    @pytest.mark.asyncio
    async def test_binary_file_integrity(self, temp_storage, test_user):
        """测试二进制文件完整性"""
        client = LocalOSSClient(base_path=temp_storage)

        # 创建包含各种字节的二进制数据
        binary_content = bytes(range(256)) * 100
        path = await client.upload(
            file_content=binary_content,
            filename="binary_test.bin",
            modality="document",
            user_id=test_user.id,
        )

        downloaded = await client.download(path)
        assert downloaded == binary_content

    @pytest.mark.asyncio
    async def test_unicode_filename(self, temp_storage, test_user):
        """测试 Unicode 文件名"""
        client = LocalOSSClient(base_path=temp_storage)

        path = await client.upload(
            file_content=b"Unicode filename test",
            filename="测试文件_中文.txt",
            modality="document",
            user_id=test_user.id,
        )

        assert path is not None
        downloaded = await client.download(path)
        assert downloaded == b"Unicode filename test"
