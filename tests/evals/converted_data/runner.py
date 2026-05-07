from __future__ import annotations

# 🧪 Converted Data 集成测试：使用 converted_data_zh 数据集测试 Mymem 记忆系统
"""
测试流程：
1. 数据导入阶段：解析 converted JSON，存储对话到记忆系统
2. 检索测试阶段：使用 QA 问题测试检索效果
3. LLM 评估阶段：LLM 生成回答 + LLM 判断正确性
4. 评估报告：计算召回率、正确率等指标，输出详细结果对比文件

使用方法：
    # 运行单个 sample 测试
    uv run python scripts/run_converted_data_eval.py --sample 0

    # 运行所有 sample 测试
    uv run python scripts/run_converted_data_eval.py --all

    # 仅导入数据（不测试）
    uv run python scripts/run_converted_data_eval.py --sample 0 --import-only
"""
import argparse
import asyncio
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

# 进度条
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        desc = kwargs.get("desc", "")
        total = kwargs.get("total", None)
        if total:
            print(f"{desc} (共 {total} 项)")
        for i, item in enumerate(iterable, 1):
            if total:
                print(f"\r{desc}: {i}/{total}", end="", flush=True)
            yield item
        if total:
            print()  # 换行

from core.database import AsyncSessionLocal
from services.llm.factory import LLMFactory
from services.llm.base import BaseLLMProvider
from services.memory.writer import MemoryWriter
from services.retrieval.retriever import MemoryRetriever
from services.constants import BASE_CATEGORIES, LEGACY_TIMELINE_CATEGORY
from services.profile_service import ProfileService
from services.chat_orchestrator import ChatOrchestrator
from schemas.onboarding_schema import OnboardingRequest, IdentityDetail, AICustomization
from repositories import UserRepository, ResourceRepository, CategoryRepository
from tables.resource import Resource
from tables.category import Category
from tables.resource_category import ResourceCategory
from tests.evals.converted_data.helpers import (
    extract_keywords,
    first_retrieved_rank,
    normalize_text,
    parse_session_date as helper_parse_session_date,
    parse_session_datetime as helper_parse_session_datetime,
)
from tests.evals.converted_data.reporting import (
    LiveResultWriter,
    calculate_metrics,
    generate_analysis_markdown,
    generate_console_report,
    generate_overall_console_report,
    save_results_json,
)
from tests.evals.converted_data.metrics import classify_answer_support_type

logger = logging.getLogger(__name__)


class EvalMode(str, Enum):
    """Evaluation layers for the converted-data harness.

    The harness keeps the project implementation real where possible:
    - unit/contract tests should live in focused pytest files.
    - storage_eval checks whether expected facts exist in DB after real writes.
    - retrieval_eval checks whether real MemoryRetriever ranks those facts.
    - assistant_eval checks retrieved-context answer generation.
    """

    STORAGE = "storage_eval"
    RETRIEVAL = "retrieval_eval"
    ASSISTANT = "assistant_eval"

# 数据集路径
REPO_ROOT = Path(__file__).parents[3]
DATA_DIR = REPO_ROOT / "data" / "converted_data_zh"

# 结果输出目录
OUTPUT_DIR = REPO_ROOT / "test_results" / "converted_data" / "legacy"

# Onboarding 画像文件
ONBOARDING_PROFILES_FILE = DATA_DIR / "sample_0_onboarding_profiles.json"


def _base_category_names() -> set[str]:
    return {category["name"] for category in BASE_CATEGORIES} | {LEGACY_TIMELINE_CATEGORY}


# ============== 数据模型 ==============

@dataclass
class SessionData:
    """单个对话会话数据"""
    session_key: str
    session_date: str
    user_character: str
    other_character: str
    content: str
    original_turns: int


@dataclass
class ConvertedData:
    """转换后的数据集"""
    user_id: str
    user_character: str
    speaker_a: str
    speaker_b: str
    total_sessions: int
    sessions: list[SessionData] = field(default_factory=list)


@dataclass
class QAQuestion:
    """QA 测试问题"""
    question: str
    answer: str
    category: int
    evidence: list[str]
    target_character: str


@dataclass
class QAData:
    """QA 测试数据集"""
    sample_index: int
    characters: list[str]
    total_questions: int
    questions: list[QAQuestion] = field(default_factory=list)


@dataclass
class RetrievalLayerInfo:
    """检索层级信息"""
    resolved_layer: str = "none"  # "category_only" / "category+resource" / "resource_only" / "none"
    llm_classified_categories: list[str] = field(default_factory=list)
    is_sufficient_at_category: bool = False  # 充足性判断是否在 Category 层就够了
    category_results_count: int = 0
    resource_results_count: int = 0
    low_confidence_fallback: bool = False


@dataclass
class TestResult:
    """单个问题的测试结果"""
    question: str
    expected_answer: str
    category: int
    evidence: list[str]
    eval_mode: str = EvalMode.ASSISTANT.value

    # 检索相关
    retrieved_contexts: list[str] = field(default_factory=list)
    retrieved_scores: list[float] = field(default_factory=list)
    retrieval_layer: RetrievalLayerInfo = field(default_factory=RetrievalLayerInfo)
    storage_hit: bool | None = None
    retrieval_hit: bool | None = None
    rank_position: int | None = None
    evaluation_trace: dict[str, Any] = field(default_factory=dict)

    # LLM 回答与评估
    llm_answer: str | None = None
    is_correct: bool | None = None
    correctness_explanation: str | None = None

    # 失败归因（规则归因 + LLM 二次验证）
    db_diagnosis: dict[str, Any] | None = None

    # 错误信息
    error: str | None = None


@dataclass
class SampleReport:
    """单个 sample 的测试报告"""
    sample_index: int
    character: str
    user_id: str
    total_sessions: int
    total_memories: int
    total_questions: int
    results: list[TestResult] = field(default_factory=list)


# ============== 数据解析 ==============

def parse_converted_file(file_path: Path) -> ConvertedData:
    """解析 converted JSON 文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sessions = []
    for s in data.get("sessions", []):
        sessions.append(SessionData(
            session_key=s.get("session_key", ""),
            session_date=s.get("session_date", ""),
            user_character=s.get("user_character", ""),
            other_character=s.get("other_character", ""),
            content=s.get("content", ""),
            original_turns=s.get("original_turns", 0),
        ))

    return ConvertedData(
        user_id=data.get("user_id", ""),
        user_character=data.get("user_character", ""),
        speaker_a=data.get("speaker_a", ""),
        speaker_b=data.get("speaker_b", ""),
        total_sessions=data.get("total_sessions", 0),
        sessions=sessions,
    )


def parse_qa_file(file_path: Path) -> QAData:
    """解析 QA JSON 文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = []
    for q in data.get("questions", []):
        questions.append(QAQuestion(
            question=q.get("question", ""),
            answer=q.get("answer", ""),
            category=q.get("category", 0),
            evidence=q.get("evidence", []),
            target_character=q.get("target_character", ""),
        ))

    return QAData(
        sample_index=data.get("sample_index", 0),
        characters=data.get("characters", []),
        total_questions=data.get("total_questions", 0),
        questions=questions,
    )


def parse_session_date(date_str: str) -> str | None:
    """将 session_date 解析为 "YYYY-MM-DD HH:MM:SS" 格式

    支持的格式：
    - "1:56 pm on 8 May, 2023" -> "2023-05-08 13:56:00"
    - "10:37 am on 27 June, 2023" -> "2023-06-27 10:37:00"
    """
    parsed = helper_parse_session_date(date_str)
    if parsed is None:
        logger.warning(f"无法解析 session_date: {date_str}")
    return parsed


def parse_session_datetime(date_str: str) -> datetime | None:
    """将 session_date 解析为 datetime，用于历史数据导入时写入数据库时间字段。"""
    return helper_parse_session_datetime(date_str)


def parse_conversation_turns(content: str) -> list[tuple[str, str]]:
    """解析对话内容为 (speaker, text) 轮次列表

    支持两种格式:
    - "user: ...\nassistant: ..."
    - "user (Name): ...\nassistant (Name): ..."
    """
    turns = []
    lines = content.strip().split("\n")

    current_speaker = None
    current_text = []

    # 匹配 "user" 或 "user (Name)" 开头的行
    speaker_pattern = re.compile(r"^(user|assistant)(?:\s*\([^)]*\))?\s*:\s*(.*)")

    for line in lines:
        match = speaker_pattern.match(line)
        if match:
            # 保存上一轮
            if current_speaker and current_text:
                turns.append((current_speaker, " ".join(current_text)))
            current_speaker = match.group(1)  # "user" 或 "assistant"
            current_text = [match.group(2).strip()]
        else:
            # 继续当前说话人的内容
            if current_speaker:
                current_text.append(line.strip())

    # 添加最后一轮
    if current_speaker and current_text:
        turns.append((current_speaker, " ".join(current_text)))

    return turns


# ============== 数据导入 ==============

async def ensure_user_onboarded(session: AsyncSession, user_id: str) -> str:
    """确保用户已完成 onboarding，不存在则创建并走完整 onboarding 流程

    user_id 是 profile key（如 sample_0_caroline），实际 username 从 profile 中读取
    """
    user_repo = UserRepository(session)

    # 先加载画像，获取真实 username
    profiles = _load_onboarding_profiles()
    profile = profiles.get(user_id)
    username = profile.get("username", user_id) if profile else user_id

    # 尝试获取已有且已完成 onboarding 的用户
    user = await user_repo.get_by_username(username)
    if user and user.user_prompt_template:
        logger.info(f"用户已存在且已 onboarding: {username}")
        request = _build_onboarding_request(user_id, profile)
        dynamic_category_names = await _resolve_dynamic_category_names(session, user.id, request)
        await _seed_dynamic_category_rows(session, user.id, dynamic_category_names)
        await session.commit()
        return user.id

    # 如果用户存在但未 onboarding，先删除再重建
    if user:
        logger.info(f"用户存在但未 onboarding，删除重建: {username}, user.id={user.id}")
        deleted = await user_repo.delete(user.id)
        logger.info(f"删除结果: {deleted}")
        await session.commit()
        session.expire_all()

    if not profile:
        # 没有 profile 时的降级处理：创建一个基本 onboarding
        logger.warning(f"未找到 {user_id} 的画像，使用默认 onboarding")
        profile = {
            "username": user_id,
            "password": "test_password",
            "identity_type": "other",
            "identity_detail": None,
            "use_cases": [],
            "interests": [],
            "ai_customization": {
                "ai_name": "小助手",
                "ai_role": "friend",
                "personality": ["温柔耐心"],
                "communication_style": "daily",
            },
        }

    # 构造 OnboardingRequest
    ai_custom = profile.get("ai_customization", {})
    request = OnboardingRequest(
        username=profile.get("username", user_id),
        password=profile.get("password", "test_password"),
        identity_type=profile.get("identity_type", "other"),
        identity_detail=IdentityDetail(**profile["identity_detail"]) if profile.get("identity_detail") else None,
        use_cases=profile.get("use_cases", []),
        interests=profile.get("interests", []),
        ai_customization=AICustomization(
            ai_name=ai_custom.get("ai_name", "小助手"),
            ai_role=ai_custom.get("ai_role", "friend"),
            personality=ai_custom.get("personality", []),
            communication_style=ai_custom.get("communication_style", "daily"),
        ),
    )

    # 调用完整的 onboarding
    llm = LLMFactory.get_provider()
    service = ProfileService(session, llm)
    result = await service.onboarding(request)

    if not result.success:
        raise RuntimeError(f"Onboarding 失败: {result.message}")

    logger.info(f"Onboarding 完成: {user_id} (user_id={result.user_id})")
    return result.user_id


def _load_onboarding_profiles() -> dict:
    """加载 onboarding 画像文件"""
    if not ONBOARDING_PROFILES_FILE.exists():
        logger.warning(f"画像文件不存在: {ONBOARDING_PROFILES_FILE}")
        return {}

    with open(ONBOARDING_PROFILES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("profiles", {})


def _build_onboarding_request(user_id: str, profile: dict[str, Any] | None) -> OnboardingRequest:
    if not profile:
        profile = {
            "username": user_id,
            "password": "test_password",
            "identity_type": "other",
            "identity_detail": None,
            "use_cases": [],
            "interests": [],
            "ai_customization": {
                "ai_name": "Assistant",
                "ai_role": "friend",
                "personality": ["patient"],
                "communication_style": "daily",
            },
        }

    ai_custom = profile.get("ai_customization", {})
    return OnboardingRequest(
        username=profile.get("username", user_id),
        password=profile.get("password", "test_password"),
        identity_type=profile.get("identity_type", "other"),
        identity_detail=IdentityDetail(**profile["identity_detail"]) if profile.get("identity_detail") else None,
        use_cases=profile.get("use_cases", []),
        interests=profile.get("interests", []),
        ai_customization=AICustomization(
            ai_name=ai_custom.get("ai_name", "Assistant"),
            ai_role=ai_custom.get("ai_role", "friend"),
            personality=ai_custom.get("personality", []),
            communication_style=ai_custom.get("communication_style", "daily"),
        ),
    )


async def _resolve_dynamic_category_names(
    session: AsyncSession,
    user_id: str,
    onboarding_request: OnboardingRequest,
) -> list[str]:
    category_repo = CategoryRepository(session)
    category_stats = await category_repo.get_category_stats(user_id)
    existing_dynamic_names = [
        name
        for name in category_stats.keys()
        if name not in _base_category_names()
    ]
    if existing_dynamic_names:
        return existing_dynamic_names

    llm = LLMFactory.get_provider()
    service = ProfileService(session, llm)
    return await service.resolve_dynamic_category_names(onboarding_request)


async def _seed_dynamic_category_rows(
    session: AsyncSession,
    user_id: str,
    dynamic_category_names: list[str],
) -> None:
    if not dynamic_category_names:
        return
    category_repo = CategoryRepository(session)
    category_stats = await category_repo.get_category_stats(user_id)
    existing_names = set(category_stats.keys())
    missing_names = [name for name in dynamic_category_names if name not in existing_names]
    if not missing_names:
        return

    llm = LLMFactory.get_provider()
    service = ProfileService(session, llm)
    await service.store_dynamic_category_seeds(user_id, missing_names)


async def import_converted_data(
    session: AsyncSession,
    converted: ConvertedData,
    enable_dedup: bool = False,
    reset_memory: bool = False,
) -> tuple[str, int]:
    """导入转换后的对话数据到记忆系统

    Returns:
        (user_id, 创建的记忆数量) — user_id 是数据库中的实际 UUID
    """
    llm = LLMFactory.get_provider()
    writer = MemoryWriter(session, llm, enable_dedup=enable_dedup)

    # 确保用户完成 onboarding
    user_id = await ensure_user_onboarded(session, converted.user_id)
    profiles = _load_onboarding_profiles()
    onboarding_request = _build_onboarding_request(converted.user_id, profiles.get(converted.user_id))
    dynamic_category_names = await _resolve_dynamic_category_names(session, user_id, onboarding_request)

    if reset_memory:
        logger.info(f"清理用户历史记忆后重新导入: user_id={user_id}")
        await session.execute(
            delete(ResourceCategory).where(
                ResourceCategory.resource_id.in_(
                    select(Resource.id).where(Resource.user_id == user_id)
                )
            )
        )
        await session.execute(delete(Category).where(Category.user_id == user_id))
        await session.execute(delete(Resource).where(Resource.user_id == user_id))
        await session.commit()
        await _seed_dynamic_category_rows(session, user_id, dynamic_category_names)
        await session.commit()

    # 获取用户的所有分类（4 基座 + 2 动态），传给 save_chat
    category_repo = CategoryRepository(session)
    category_stats = await category_repo.get_category_stats(user_id)
    categories_for_prompt = list(BASE_CATEGORIES)
    for name in category_stats.keys():
        if name not in _base_category_names():
            categories_for_prompt.append({"name": name, "description": f"User-specific memories related to {name}"})
    logger.info(f"用户分类列表: {[c['name'] for c in categories_for_prompt]}")

    memory_count = 0

    pbar_import = tqdm(
        enumerate(converted.sessions),
        total=len(converted.sessions),
        desc=f"导入对话 [{converted.user_character}]",
        unit="session",
    )

    for i, sess in pbar_import:
        # 解析对话轮次
        turns = parse_conversation_turns(sess.content)

        # 解析 session_date 作为 reference_time，确保历史对话的时间推断正确
        reference_time = parse_session_date(sess.session_date)
        memory_time = parse_session_datetime(sess.session_date)
        if reference_time:
            logger.debug(f"Session {i}: reference_time={reference_time}")

        # 将相邻的 user-assistant 配对保存
        j = 0
        while j < len(turns) - 1:
            if turns[j][0] == "user" and turns[j + 1][0] == "assistant":
                user_input = turns[j][1]
                assistant_response = turns[j + 1][1]

                try:
                    result = await writer.save_chat(
                        user_id=user_id,
                        user_input=user_input,
                        assistant_response=assistant_response,
                        modality="text",
                        user_categories=categories_for_prompt,
                        reference_time=reference_time,
                        memory_time=memory_time,
                    )
                    memory_count += 1

                    if memory_count % 10 == 0:
                        await session.commit()

                    pbar_import.set_postfix_str(f"mem={memory_count}", refresh=False)

                except Exception as e:
                    logger.error(f"导入记忆失败: {e}")
                    await session.rollback()

                j += 2
            else:
                j += 1

    await session.commit()
    return user_id, memory_count




def _normalize_text(text: str) -> str:
    return normalize_text(text)


def _extract_keywords(question: str, standard_answer: str, evidence: list[str], limit: int = 8) -> list[str]:
    """从问题/标准答案/evidence 中提取可用于规则归因的关键词（中文优先）"""
    return extract_keywords(question, standard_answer, evidence, limit)


async def _query_db_related_memories(
    session: AsyncSession,
    user_id: str,
    keywords: list[str],
    limit_each: int = 20,
) -> dict[str, list[dict[str, Any]]]:
    """在 Resource / Category 中按关键词进行规则检索，返回候选记忆片段"""
    if not keywords:
        return {"resources": [], "categories": []}

    resources: dict[str, dict[str, Any]] = {}
    categories: dict[str, dict[str, Any]] = {}

    for kw in keywords:
        like_kw = f"%{kw}%"

        res_result = await session.execute(
            select(
                Resource.id,
                Resource.description,
                Resource.raw_content,
                Resource.importance_score,
                Resource.updated_at,
            )
            .where(
                Resource.user_id == user_id,
                Resource.description.is_not(None),
                Resource.description.ilike(like_kw),
            )
            .order_by(Resource.importance_score.desc(), Resource.updated_at.desc())
            .limit(limit_each)
        )
        for row in res_result.fetchall():
            rid = row[0]
            if rid not in resources:
                resources[rid] = {
                    "id": rid,
                    "source": "resource",
                    "text": row[1] or row[2] or "",
                    "importance_score": row[3],
                    "updated_at": row[4].isoformat() if row[4] else None,
                    "matched_keyword": kw,
                }

        cat_result = await session.execute(
            select(
                Category.id,
                Category.category_name,
                Category.content,
                Category.importance_score,
                Category.updated_at,
            )
            .where(
                Category.user_id == user_id,
                Category.content.ilike(like_kw),
            )
            .order_by(Category.importance_score.desc(), Category.updated_at.desc())
            .limit(limit_each)
        )
        for row in cat_result.fetchall():
            cid = row[0]
            if cid not in categories:
                categories[cid] = {
                    "id": cid,
                    "source": "category",
                    "category_name": row[1],
                    "text": row[2] or "",
                    "importance_score": row[3],
                    "updated_at": row[4].isoformat() if row[4] else None,
                    "matched_keyword": kw,
                }

    return {
        "resources": list(resources.values()),
        "categories": list(categories.values()),
    }


async def _llm_verify_db_memories_can_answer(
    llm: BaseLLMProvider,
    question: str,
    standard_answer: str,
    db_memories: list[dict[str, Any]],
) -> dict[str, Any]:
    """仅在 DB 有命中但检索未召回时，对 DB 片段做 LLM 二次可回答性验证"""
    if not db_memories:
        return {"can_answer": None, "reason": "no_db_memories"}

    memory_lines = []
    for idx, m in enumerate(db_memories, 1):
        source = m.get("source", "unknown")
        cat = m.get("category_name")
        prefix = f"[{idx}][{source}]"
        if cat:
            prefix += f"[{cat}]"
        text_snippet = (m.get("text") or "")[:400]
        memory_lines.append(f"{prefix} {text_snippet}")

    memory_text = "\n".join(memory_lines)

    prompt = f"""你是记忆系统诊断评估器。请判断给定数据库记忆片段是否足以回答问题。

问题：{question}
标准答案：{standard_answer}

数据库命中记忆片段：
{memory_text}

请输出：
<can_answer>YES</can_answer> 或 <can_answer>NO</can_answer>
<reason>不超过80字，说明依据</reason>
"""

    try:
        response = await llm.generate_chat_response(
            system_prompt="你是严谨的检索诊断专家，只基于给定片段判断可回答性。",
            context="",
            user_query=prompt,
        )
        can_answer_match = re.search(r"<can_answer>(.*?)</can_answer>", response, re.DOTALL | re.IGNORECASE)
        can_answer_text = can_answer_match.group(1).strip().upper() if can_answer_match else ""
        can_answer = can_answer_text == "YES"
        reason_match = re.search(r"<reason>(.*?)</reason>", response, re.DOTALL | re.IGNORECASE)
        reason = reason_match.group(1).strip() if reason_match else "未提供原因"
        return {
            "can_answer": can_answer,
            "reason": reason,
            "raw": response,
        }
    except Exception as e:
        logger.error(f"LLM 二次验证失败: {e}")
        return {
            "can_answer": None,
            "reason": f"llm_verification_error: {e}",
        }


async def diagnose_bad_case(
    session: AsyncSession,
    llm: BaseLLMProvider,
    user_id: str,
    question: str,
    standard_answer: str,
    evidence: list[str],
    retrieved_contexts: list[str],
    retrieval_layer: RetrievalLayerInfo | None = None,
    max_db_snippets: int = 5,
) -> dict[str, Any]:
    """失败样本归因：规则归因 +（条件触发）LLM 二次验证"""
    keywords = _extract_keywords(question, standard_answer, evidence)
    db_hits = await _query_db_related_memories(session, user_id, keywords)

    db_memories = [*db_hits["resources"], *db_hits["categories"]]
    db_memories_sorted = sorted(
        db_memories,
        key=lambda x: (x.get("importance_score") or 0),
        reverse=True,
    )[:max_db_snippets]

    retrieved_norm = [_normalize_text(c) for c in retrieved_contexts if c]

    matched_in_retrieved = []
    missed_in_retrieval = []
    for m in db_memories_sorted:
        text_norm = _normalize_text(m.get("text", ""))
        if any(text_norm and text_norm in rc for rc in retrieved_norm):
            matched_in_retrieved.append(m)
        else:
            missed_in_retrieval.append(m)

    if not db_memories_sorted:
        diagnosis_type = "storage_gap"
        summary = "数据库未命中可支持答案的记忆，倾向存储/抽取阶段缺失"
    elif missed_in_retrieval:
        diagnosis_type = "retrieval_gap"
        summary = "数据库命中相关记忆但未被检索召回，倾向检索/排序失效"
    else:
        diagnosis_type = "generation_or_eval_gap"
        summary = "数据库相关记忆已召回，倾向回答生成或正确性评估链路问题"

    llm_verification = None
    if diagnosis_type == "retrieval_gap":
        llm_verification = await _llm_verify_db_memories_can_answer(
            llm=llm,
            question=question,
            standard_answer=standard_answer,
            db_memories=missed_in_retrieval,
        )

    retrieval_failure_analysis = None
    if diagnosis_type == "retrieval_gap":
        if (
            retrieval_layer
            and retrieval_layer.resolved_layer == "category_only"
            and retrieval_layer.is_sufficient_at_category
            and llm_verification
            and llm_verification.get("can_answer") is True
        ):
            retrieval_failure_analysis = {
                "failure_stage": "category_sufficiency_gate",
                "likely_root_cause": "sufficiency_false_positive",
                "confidence": "high",
                "explanation": (
                    "当前 trace 可以直接支持：category 层被判定为“足够”，系统没有继续走 resource fallback；"
                    "但数据库中又存在足以直接回答问题的证据。"
                    "因此失败链路更接近 category_only 提前截断，而不是回答模型自由发挥。"
                ),
                "embedding_vs_scoring": (
                    "这不能单独证明是 embedding 模型故障。更可能是两段式链路共同导致："
                    "category top-k 没把正确证据排上来，而 sufficiency 误判又阻止了后续补救检索。"
                ),
            }
        elif llm_verification and llm_verification.get("can_answer") is True:
            retrieval_failure_analysis = {
                "failure_stage": "retrieval",
                "likely_root_cause": "ranking_or_filtering_gap",
                "confidence": "high",
                "explanation": (
                    "当前 trace 可以直接支持：数据库里已有足以回答的问题证据，但这些证据没有进入最终检索结果。"
                    "这说明失败首先发生在召回/排序链路，而不是回答阶段。"
                ),
                "embedding_vs_scoring": (
                    "仅凭当前 trace 不能把原因唯一归到 embedding 模型本身。"
                    "更稳妥的解释是：category/resource 检索与排序没有把正确记忆顶到 top-k，"
                    "可能由向量区分度不足、四因子评分排序、或上层过滤共同造成。"
                ),
            }
        else:
            retrieval_failure_analysis = {
                "failure_stage": "diagnosis",
                "likely_root_cause": "db_keyword_probe_noise_or_partial_match",
                "confidence": "medium",
                "explanation": (
                    "数据库关键词探针命中了部分相关记忆，但这批命中片段本身不足以直接回答问题。"
                    "因此这条 trace 不能高置信断言为纯检索失败，还需要结合更精确的关键词或人工核查。"
                ),
                "embedding_vs_scoring": (
                    "当前证据不足以区分 embedding 问题还是排序问题，"
                    "更可能是 DB 诊断关键词过宽导致的候选污染。"
                ),
            }

    return {
        "diagnosis_type": diagnosis_type,
        "summary": summary,
        "keywords": keywords,
        "db_hits": {
            "resource_count": len(db_hits["resources"]),
            "category_count": len(db_hits["categories"]),
        },
        "db_memories_sample": db_memories_sorted,
        "matched_in_retrieved": matched_in_retrieved,
        "missed_in_retrieval": missed_in_retrieval,
        "llm_verification": llm_verification,
        "retrieval_failure_analysis": retrieval_failure_analysis,
    }


async def evaluate_answer_correctness(
    llm: BaseLLMProvider,
    question: str,
    generated_answer: str,
    standard_answer: str,
) -> tuple[bool, str]:
    """使用 LLM 评估生成答案是否正确"""
    prompt = f"""You are an answer evaluator. Determine if the generated answer correctly answers the question based on the standard answer.

Question: {question}

Standard Answer: {standard_answer}

Generated Answer: {generated_answer}

Evaluate if the generated answer contains the key information from the standard answer. Be lenient with phrasing differences but strict about factual accuracy.

Respond in this format:
<judgement>CORRECT</judgement> or <judgement>INCORRECT</judgement>
<explanation>Brief explanation of your judgement</explanation>
"""

    try:
        response = await llm.generate_chat_response(
            system_prompt="You are an answer evaluator. Judge correctness based on factual accuracy.",
            context="",
            user_query=prompt,
        )

        is_correct = "<judgement>CORRECT</judgement>".upper() in response.upper()
        match = re.search(r"<explanation>(.*?)</explanation>", response, re.DOTALL | re.IGNORECASE)
        explanation = match.group(1).strip() if match else "No explanation provided"
        return is_correct, explanation

    except Exception as e:
        logger.error(f"LLM 评估失败: {e}")
        return False, f"Evaluation error: {e}"


# ============== 检索测试 ==============

async def generate_answer_with_chat_orchestrator(
    session: AsyncSession,
    llm: BaseLLMProvider,
    user: Any | None,
    user_id: str,
    question: str,
    top_k: int = 15,
    retrieved_results: list[dict[str, Any]] | None = None,
) -> str:
    """Generate assistant_eval answers through the real production chat orchestration path."""
    orchestrator = ChatOrchestrator(session, llm)
    chunks: list[str] = []
    try:
        async for chunk in orchestrator.stream(
            user_id=user_id,
            user_query=question,
            user_prompt_template=getattr(user, "user_prompt_template", None) if user else None,
            agent_persona_template=getattr(user, "agent_persona_template", None) if user else None,
            pending_chats=[],
            top_k=top_k,
            retrieved_results=retrieved_results,
        ):
            chunks.append(chunk)
    except Exception as e:
        logger.error(f"ChatOrchestrator answer generation failed: {e}")
        return f"Error generating answer through ChatOrchestrator: {e}"

    answer = "".join(chunks).strip()
    return answer or "I don't have enough information to answer this question."


async def postprocess_bad_case_diagnoses(
    session: AsyncSession,
    user_id: str,
    results: list[TestResult],
    eval_mode: EvalMode,
) -> None:
    """Populate db_diagnosis after the main evaluation loop, only for failed cases."""
    if eval_mode == EvalMode.STORAGE:
        return

    llm = LLMFactory.get_provider()
    for result in results:
        if result.error or result.db_diagnosis is not None:
            continue
        if result.is_correct is not False:
            continue

        try:
            result.db_diagnosis = await diagnose_bad_case(
                session=session,
                llm=llm,
                user_id=user_id,
                question=result.question,
                standard_answer=result.expected_answer,
                evidence=result.evidence,
                retrieved_contexts=result.retrieved_contexts,
                retrieval_layer=result.retrieval_layer,
            )
        except Exception as exc:
            logger.error("Postprocess bad-case diagnosis failed: %s - %s", result.question, exc)
            result.db_diagnosis = {
                "diagnosis_type": "db_diagnosis_error",
                "summary": f"DB diagnosis error: {exc}",
                "llm_verification": None,
            }


def _extract_retrieval_observation(retrieved: list[dict]) -> tuple[list[str], list[float], RetrievalLayerInfo]:
    """Convert real MemoryRetriever results into stable test observation fields."""
    contexts = []
    scores = []
    layer_info = RetrievalLayerInfo()

    has_category_result = False
    has_resource_result = False
    llm_categories_seen = set()

    for r in retrieved:
        resource = r.get("resource")
        category = r.get("category")
        score = r.get("score", 0)
        strategy = r.get("strategy", "")
        if r.get("low_confidence_fallback"):
            layer_info.low_confidence_fallback = True

        if strategy == "category_source_expansion" and resource and category:
            context = f"[{category.category_name}] fact: {category.content}"
            if resource.description:
                context += f" | source_description: {resource.description}"
            if resource.raw_content:
                context += f" | source_raw_content: {resource.raw_content}"
            contexts.append(context)
            scores.append(score)
        elif resource and resource.description:
            contexts.append(resource.description)
            scores.append(score)
        elif category and category.content:
            contexts.append(category.content)
            scores.append(score)

        if strategy == "category_vector":
            has_category_result = True
            if category:
                llm_categories_seen.add(category.category_name)
        elif strategy in {"resource_vector", "category_source_expansion"}:
            has_resource_result = True
            if category:
                llm_categories_seen.add(category.category_name)
        elif strategy == "vector":
            has_resource_result = True

    layer_info.llm_classified_categories = sorted(llm_categories_seen)
    layer_info.category_results_count = sum(1 for r in retrieved if r.get("strategy") == "category_vector")
    layer_info.resource_results_count = sum(
        1
        for r in retrieved
        if r.get("strategy") in {"resource_vector", "category_source_expansion"}
    )

    if has_category_result and has_resource_result:
        layer_info.resolved_layer = "category+resource"
        layer_info.is_sufficient_at_category = False
    elif has_category_result:
        layer_info.resolved_layer = "category_only"
        layer_info.is_sufficient_at_category = True
    elif has_resource_result:
        layer_info.resolved_layer = "resource_only"
        layer_info.is_sufficient_at_category = False
    else:
        layer_info.resolved_layer = "none"
        layer_info.is_sufficient_at_category = False

    return contexts, scores, layer_info


def _first_retrieved_rank(db_memories: list[dict[str, Any]], contexts: list[str]) -> int | None:
    """Return 1-based rank for the first retrieved context matching a DB memory."""
    return first_retrieved_rank(db_memories, contexts)


async def _evaluate_storage_layer(
    session: AsyncSession,
    user_id: str,
    q: QAQuestion,
) -> dict[str, Any]:
    """Storage contract check: did real writes create any DB evidence for this QA?"""
    keywords = _extract_keywords(q.question, q.answer, q.evidence)
    db_hits = await _query_db_related_memories(session, user_id, keywords)
    db_memories = [*db_hits["resources"], *db_hits["categories"]]
    db_memories_sorted = sorted(
        db_memories,
        key=lambda x: (x.get("importance_score") or 0),
        reverse=True,
    )
    return {
        "storage_hit": bool(db_memories_sorted),
        "keywords": keywords,
        "db_hits": {
            "resource_count": len(db_hits["resources"]),
            "category_count": len(db_hits["categories"]),
        },
        "db_memories_sample": db_memories_sorted[:5],
    }


def _result_to_live_dict(result: TestResult) -> dict[str, Any]:
    return {
        "eval_mode": result.eval_mode,
        "question": result.question,
        "standard_answer": result.expected_answer,
        "generated_answer": result.llm_answer,
        "is_correct": result.is_correct,
        "correctness_explanation": result.correctness_explanation,
        "category": result.category,
        "evidence": result.evidence,
        "storage_hit": result.storage_hit,
        "retrieval_hit": result.retrieval_hit,
        "rank_position": result.rank_position,
        "answer_support_type": classify_answer_support_type(
            {
                "question": result.question,
                "standard_answer": result.expected_answer,
                "is_correct": result.is_correct,
                "retrieval_hit": result.retrieval_hit,
            }
        ),
        "evaluation_trace": result.evaluation_trace,
        "retrieval_layer": {
            "resolved_layer": result.retrieval_layer.resolved_layer,
            "is_sufficient_at_category": result.retrieval_layer.is_sufficient_at_category,
            "llm_classified_categories": result.retrieval_layer.llm_classified_categories,
            "category_results_count": result.retrieval_layer.category_results_count,
            "resource_results_count": result.retrieval_layer.resource_results_count,
            "low_confidence_fallback": result.retrieval_layer.low_confidence_fallback,
        },
        "retrieved_contexts": result.retrieved_contexts[:5],
        "retrieved_scores": [round(s, 4) for s in result.retrieved_scores[:5]],
        "db_diagnosis": result.db_diagnosis,
        "error": result.error,
    }


async def legacy_test_retrieval(
    session: AsyncSession,
    user_id: str,
    qa_data: QAData,
    top_k: int = 15,
    live_writer: LiveResultWriter | None = None,
    eval_mode: EvalMode = EvalMode.ASSISTANT,
) -> list[TestResult]:
    """Compatibility wrapper for older callers.

    Keep this name importable, but route behavior through the official layered
    evaluator so assistant answers always use ChatOrchestrator.
    """
    return await run_layered_qa_evaluation(
        session=session,
        user_id=user_id,
        qa_data=qa_data,
        top_k=top_k,
        live_writer=live_writer,
        eval_mode=eval_mode,
    )


async def run_layered_qa_evaluation(
    session: AsyncSession,
    user_id: str,
    qa_data: QAData,
    top_k: int = 15,
    live_writer: LiveResultWriter | None = None,
    eval_mode: EvalMode = EvalMode.ASSISTANT,
) -> list[TestResult]:
    """Run the converted-data harness in one explicit evaluation mode.

    storage_eval checks the real write path's DB evidence.
    retrieval_eval checks the real MemoryRetriever top-k result.
    assistant_eval checks answer generation from retrieved memories.
    """
    llm = LLMFactory.get_provider()
    retriever = MemoryRetriever(session, llm)
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    results = []
    total = qa_data.total_questions
    pbar = tqdm(
        enumerate(qa_data.questions, 1),
        total=total,
        desc=f"QA {eval_mode.value}",
        unit="question",
    )

    for _, q in pbar:
        result = TestResult(
            question=q.question,
            expected_answer=q.answer,
            category=q.category,
            evidence=q.evidence,
            eval_mode=eval_mode.value,
        )

        try:
            storage_trace = await _evaluate_storage_layer(session, user_id, q)
            result.storage_hit = storage_trace["storage_hit"]
            result.evaluation_trace["storage_eval"] = storage_trace

            retrieved: list[dict] = []
            contexts: list[str] = []

            if eval_mode == EvalMode.STORAGE:
                result.is_correct = result.storage_hit
                result.correctness_explanation = (
                    "Storage evidence found in DB."
                    if result.storage_hit
                    else "No DB evidence found for expected answer keywords/evidence."
                )
                if not result.storage_hit:
                    result.db_diagnosis = {
                        "diagnosis_type": "storage_gap",
                        "summary": "No DB evidence found in storage_eval.",
                        **storage_trace,
                    }
            else:
                retrieved = await retriever.retrieve(
                    user_id=user_id,
                    query=q.question,
                    top_k=top_k,
                    use_llm_classification=True,
                )
                contexts, scores, layer_info = _extract_retrieval_observation(retrieved)
                result.retrieved_contexts = contexts
                result.retrieved_scores = scores
                result.retrieval_layer = layer_info

                db_memories = storage_trace.get("db_memories_sample", [])
                result.rank_position = _first_retrieved_rank(db_memories, contexts)
                result.retrieval_hit = result.rank_position is not None

                if eval_mode == EvalMode.RETRIEVAL:
                    result.is_correct = result.retrieval_hit
                    result.correctness_explanation = (
                        f"DB evidence retrieved at rank {result.rank_position}."
                        if result.retrieval_hit
                        else "DB evidence exists but did not appear in retrieved top-k."
                    )
                elif contexts:
                    result.llm_answer = await generate_answer_with_chat_orchestrator(
                        session=session,
                        llm=llm,
                        user=user,
                        user_id=user_id,
                        question=q.question,
                        top_k=top_k,
                        retrieved_results=retrieved,
                    )
                    is_correct, explanation = await evaluate_answer_correctness(
                        llm, q.question, result.llm_answer, q.answer,
                    )
                    result.is_correct = is_correct
                    result.correctness_explanation = explanation
                else:
                    result.is_correct = False
                    result.correctness_explanation = "No retrieved context available for assistant answer generation."
        except Exception as e:
            logger.error(f"Layered QA evaluation failed: {q.question} - {e}")
            result.error = str(e)

        results.append(result)

        if live_writer:
            live_writer.add_qa_result(_result_to_live_dict(result))

        correct_so_far = sum(1 for r in results if r.is_correct)
        evaluated_so_far = sum(1 for r in results if r.is_correct is not None)
        acc_str = f"{correct_so_far}/{evaluated_so_far}" if evaluated_so_far else "-"
        layer_str = result.retrieval_layer.resolved_layer
        mark = "?" if result.is_correct is None else ("Y" if result.is_correct else "N")
        pbar.set_postfix_str(f"ok={acc_str} layer={layer_str} [{mark}]", refresh=False)

    return results





async def run_single_sample(
    sample_index: int,
    import_only: bool = False,
    retrieval_only: bool = False,
    enable_dedup: bool = False,
    top_k: int = 15,
    character_filter: str | None = None,
    reset_memory: bool = False,
    eval_mode: EvalMode = EvalMode.ASSISTANT,
    max_questions: int | None = None,
    postprocess_bad_cases: bool = False,
) -> list[SampleReport]:
    """运行单个 sample 的测试"""
    # 查找对应文件
    converted_files = sorted(DATA_DIR.glob(f"sample_{sample_index}_*_converted.json"))
    qa_file = DATA_DIR / f"sample_{sample_index}_qa.json"

    # 按角色过滤
    if character_filter:
        char_lower = character_filter.lower()
        converted_files = [f for f in converted_files if char_lower in f.name.lower()]
        logger.info(f"角色过滤: {character_filter}, 匹配 {len(converted_files)} 个文件")

    if not converted_files:
        logger.error(f"未找到 sample_{sample_index} 的数据文件")
        return []

    if not qa_file.exists() and not import_only:
        logger.error(f"未找到 sample_{sample_index} 的 QA 文件")
        return []

    reports = []
    live_writer = (
        LiveResultWriter(
            OUTPUT_DIR,
            prefix=f"mymem_{eval_mode.value}",
            eval_mode=eval_mode.value,
        )
        if not import_only
        else None
    )

    async with AsyncSessionLocal() as session:
        for converted_file in converted_files:
            # 解析数据
            converted = parse_converted_file(converted_file)
            logger.info(f"加载数据: {converted_file.name} ({converted.total_sessions} sessions)")

            # 导入数据
            if retrieval_only:
                # 从数据库查找已有用户的 UUID
                user_repo = UserRepository(session)
                profiles = _load_onboarding_profiles()
                profile = profiles.get(converted.user_id)
                username = profile.get("username", converted.user_id) if profile else converted.user_id
                user = await user_repo.get_by_username(username)
                if not user:
                    logger.error(f"用户 {username} 不存在，无法仅检索。请先导入数据。")
                    continue
                real_user_id = user.id
                # 统计已有记忆数
                from repositories.resource_repository import ResourceRepository
                res_repo = ResourceRepository(session)
                memory_count = len(await res_repo.get_by_user_id(real_user_id))
                logger.info(f"跳过导入，使用已有数据: user_id={real_user_id}, {memory_count} 条记忆")
            else:
                real_user_id, memory_count = await import_converted_data(
                    session,
                    converted,
                    enable_dedup=enable_dedup,
                    reset_memory=reset_memory,
                )
                logger.info(f"导入完成: {memory_count} 条记忆, user_id={real_user_id}")

            if import_only:
                continue

            # 解析 QA 数据
            qa_data = parse_qa_file(qa_file)
            # 过滤只针对当前角色的问题
            qa_filtered = QAData(
                sample_index=qa_data.sample_index,
                characters=qa_data.characters,
                total_questions=0,
                questions=[q for q in qa_data.questions if q.target_character == converted.user_character],
            )
            if max_questions is not None:
                qa_filtered.questions = qa_filtered.questions[:max_questions]
            qa_filtered.total_questions = len(qa_filtered.questions)

            logger.info(f"测试 QA: {qa_filtered.total_questions} 个问题 (角色: {converted.user_character})")
            print(f"\n{'='*60}")
            print(f"开始检索测试: {converted.user_character} ({qa_filtered.total_questions} 个问题)")
            print(f"结果实时写入: {live_writer.results_path}")
            print(f"{'='*60}")

            # 开始 live writer 的 sample
            if live_writer:
                live_writer.start_sample(
                    sample_index=sample_index,
                    character=converted.user_character,
                    user_id=real_user_id,
                    total_sessions=converted.total_sessions,
                    total_memories=memory_count,
                    total_questions=qa_filtered.total_questions,
                )

            # 执行检索测试（含 LLM 生成回答 + LLM 评估）
            try:
                results = await run_layered_qa_evaluation(
                    session,
                    real_user_id,
                    qa_filtered,
                    top_k=top_k,
                    live_writer=live_writer,
                    eval_mode=eval_mode,
                )
                if postprocess_bad_cases:
                    await postprocess_bad_case_diagnoses(
                        session=session,
                        user_id=real_user_id,
                        results=results,
                        eval_mode=eval_mode,
                    )
                    if live_writer:
                        live_writer.replace_current_sample_results(
                            [_result_to_live_dict(result) for result in results]
                        )
            except Exception:
                if live_writer:
                    live_writer.finish_sample(status="interrupted")
                raise
            else:
                if live_writer:
                    live_writer.finish_sample(status="completed")

            # 生成报告
            report = SampleReport(
                sample_index=sample_index,
                character=converted.user_character,
                user_id=real_user_id,
                total_sessions=converted.total_sessions,
                total_memories=memory_count,
                total_questions=qa_filtered.total_questions,
                results=results,
            )
            reports.append(report)

            # 打印单个角色报告
            print(generate_console_report(report, eval_mode=eval_mode.value))

    if live_writer and reports:
        print(f"\n详细结果文件: {live_writer.results_path}")

    return reports


async def run_all_samples(
    import_only: bool = False,
    retrieval_only: bool = False,
    enable_dedup: bool = False,
    reset_memory: bool = False,
    eval_mode: EvalMode = EvalMode.ASSISTANT,
    max_questions: int | None = None,
    postprocess_bad_cases: bool = False,
) -> None:
    """运行所有 sample 的测试"""
    # 查找所有 sample
    sample_indices = set()
    for f in DATA_DIR.glob("sample_*_converted.json"):
        # 提取 sample index
        match = re.match(r"sample_(\d+)_", f.name)
        if match:
            sample_indices.add(int(match.group(1)))

    sample_indices = sorted(sample_indices)
    logger.info(f"发现 {len(sample_indices)} 个 sample: {sample_indices}")

    all_reports = []

    for idx in sample_indices:
        logger.info(f"\n{'=' * 60}\n开始测试 Sample {idx}\n{'=' * 60}")
        reports = await run_single_sample(
            idx,
            import_only=import_only,
            retrieval_only=retrieval_only,
            enable_dedup=enable_dedup,
            reset_memory=reset_memory,
            eval_mode=eval_mode,
            max_questions=max_questions,
            postprocess_bad_cases=postprocess_bad_cases,
        )
        all_reports.extend(reports)

    # 保存结果对比文件
    if all_reports and not import_only:
        results_path = save_results_json(all_reports, OUTPUT_DIR, eval_mode=eval_mode.value)

        # 自动生成分析报告（失败不影响测试主流程）
        llm = LLMFactory.get_provider()
        analysis_path = await generate_analysis_markdown(llm, results_path)

        # 打印总体报告
        all_results = [r for report in all_reports for r in report.results]
        overall_metrics = calculate_metrics(all_results, eval_mode=eval_mode.value)

        print("\n" + generate_overall_console_report(overall_metrics, eval_mode=eval_mode.value))
        print("")
        print(f"详细结果文件: {results_path}")
        if analysis_path:
            print(f"分析报告文件: {analysis_path}")


# ============== 入口 ==============

def main():
    global DATA_DIR, ONBOARDING_PROFILES_FILE

    parser = argparse.ArgumentParser(description="使用 converted_data_zh 数据集测试 Mymem 记忆系统")
    parser.add_argument("--sample", type=int, help="指定要测试的 sample index")
    parser.add_argument("--all", action="store_true", help="运行所有 sample 测试")
    parser.add_argument("--data-dir", type=Path, help="指定测试数据目录（默认 data/converted_data_zh）")
    parser.add_argument("--import-only", action="store_true", help="仅导入数据，不执行测试")
    parser.add_argument("--retrieval-only", action="store_true", help="跳过导入，仅执行检索测试（使用已有数据）")
    parser.add_argument("--reset-memory", action="store_true", help="导入前清空该测试用户的历史记忆，避免旧污染数据影响测试")
    parser.add_argument("--no-dedup", action="store_true", help="禁用记忆去重")
    parser.add_argument("--top-k", type=int, default=15, help="检索返回数量 (默认: 15)")
    parser.add_argument("--character", type=str, help="只测试指定角色（如 caroline、melanie）")
    parser.add_argument("--max-questions", type=int, help="限制每个角色的 QA 数量，用于端到端冒烟测试")
    parser.add_argument("--postprocess-bad-cases", action="store_true", help="主评估完成后再补做失败样本的 bad-case diagnosis")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细日志")

    parser.add_argument(
        "--eval-mode",
        choices=[mode.value for mode in EvalMode],
        default=EvalMode.ASSISTANT.value,
        help="Evaluation mode: storage_eval, retrieval_eval, or assistant_eval.",
    )

    args = parser.parse_args()
    eval_mode = EvalMode(args.eval_mode)

    if args.data_dir:
        DATA_DIR = args.data_dir
        ONBOARDING_PROFILES_FILE = DATA_DIR / "sample_0_onboarding_profiles.json"

    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # 运行测试
    if args.all:
        asyncio.run(run_all_samples(
            import_only=args.import_only,
            retrieval_only=args.retrieval_only,
            enable_dedup=not args.no_dedup,
            reset_memory=args.reset_memory,
            eval_mode=eval_mode,
            max_questions=args.max_questions,
            postprocess_bad_cases=args.postprocess_bad_cases,
        ))
    elif args.sample is not None:
        reports = asyncio.run(run_single_sample(
            args.sample,
            import_only=args.import_only,
            retrieval_only=args.retrieval_only,
            enable_dedup=not args.no_dedup,
            top_k=args.top_k,
            character_filter=args.character,
            reset_memory=args.reset_memory,
            eval_mode=eval_mode,
            max_questions=args.max_questions,
            postprocess_bad_cases=args.postprocess_bad_cases,
        ))

        if reports and not args.import_only:
            results_path = save_results_json(reports, OUTPUT_DIR, eval_mode=eval_mode.value)
            llm = LLMFactory.get_provider()
            analysis_path = asyncio.run(generate_analysis_markdown(llm, results_path))
            print(f"详细结果文件: {results_path}")
            if analysis_path:
                print(f"分析报告文件: {analysis_path}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

