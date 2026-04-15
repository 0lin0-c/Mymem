# 🧪 Converted Data 集成测试：使用 converted_data_zh 数据集测试 Mymem 记忆系统
"""
测试流程：
1. 数据导入阶段：解析 converted JSON，存储对话到记忆系统
2. 检索测试阶段：使用 QA 问题测试检索效果
3. 评估报告：计算召回率、精确率等指标

使用方法：
    # 运行单个 sample 测试
    uv run python -m tests.test_converted_data --sample 0

    # 运行所有 sample 测试
    uv run python -m tests.test_converted_data --all

    # 仅导入数据（不测试）
    uv run python -m tests.test_converted_data --sample 0 --import-only
"""
import argparse
import asyncio
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from services.llm.factory import LLMFactory
from services.memory.writer import MemoryWriter
from services.retrieval.retriever import MemoryRetriever
from repositories import UserRepository, ResourceRepository, CategoryRepository

logger = logging.getLogger(__name__)

# 数据集路径
DATA_DIR = Path(__file__).parent.parent.parent / "memU" / "tier_test_results" / "converted_data_zh"


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
class TestResult:
    """单个问题的测试结果"""
    question: str
    expected_answer: str
    retrieved_contexts: list[str]
    retrieved_scores: list[float]
    is_relevant: bool  # 检索结果是否包含相关信息
    llm_answer: str | None = None  # LLM 基于检索结果的回答
    is_correct: bool | None = None  # LLM 回答是否正确


@dataclass
class SampleReport:
    """单个 sample 的测试报告"""
    sample_index: int
    character: str
    total_sessions: int
    total_memories: int
    total_questions: int
    results: list[TestResult] = field(default_factory=list)

    # 指标
    recall_at_k: float = 0.0  # Top-k 召回率
    mrr: float = 0.0  # Mean Reciprocal Rank
    avg_retrieval_score: float = 0.0


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


def parse_conversation_turns(content: str) -> list[tuple[str, str]]:
    """解析对话内容为 (speaker, text) 轮次列表

    格式: "user: ...\nassistant: ...\nuser: ..."
    """
    turns = []
    lines = content.strip().split("\n")

    current_speaker = None
    current_text = []

    for line in lines:
        # 检测说话人切换
        if line.startswith("user:"):
            if current_speaker and current_text:
                turns.append((current_speaker, " ".join(current_text)))
            current_speaker = "user"
            current_text = [line[5:].strip()]  # 去掉 "user:" 前缀
        elif line.startswith("assistant:"):
            if current_speaker and current_text:
                turns.append((current_speaker, " ".join(current_text)))
            current_speaker = "assistant"
            current_text = [line[10:].strip()]  # 去掉 "assistant:" 前缀
        else:
            # 继续当前说话人的内容
            if current_speaker:
                current_text.append(line.strip())

    # 添加最后一轮
    if current_speaker and current_text:
        turns.append((current_speaker, " ".join(current_text)))

    return turns


# ============== 数据导入 ==============

async def ensure_user_exists(session: AsyncSession, user_id: str, character_name: str) -> str:
    """确保用户存在，不存在则创建"""
    user_repo = UserRepository(session)

    # 尝试获取现有用户
    user = await user_repo.get_by_id(user_id)
    if user:
        return user.id

    # 创建新用户
    user = await user_repo.create(
        username=user_id,
        password="test_password",  # 测试用密码
    )
    await session.commit()
    logger.info(f"创建用户: {user_id} ({character_name})")
    return user.id


async def import_converted_data(
    session: AsyncSession,
    converted: ConvertedData,
    enable_dedup: bool = False,
) -> int:
    """导入转换后的对话数据到记忆系统

    Returns:
        创建的记忆数量
    """
    llm = LLMFactory.get_provider()
    writer = MemoryWriter(session, llm, enable_dedup=enable_dedup)

    # 确保用户存在
    user_id = await ensure_user_exists(session, converted.user_id, converted.user_character)

    memory_count = 0

    for i, sess in enumerate(converted.sessions):
        # 解析对话轮次
        turns = parse_conversation_turns(sess.content)

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
                    )
                    memory_count += 1

                    if memory_count % 10 == 0:
                        logger.info(f"已导入 {memory_count} 条记忆...")
                        await session.commit()

                except Exception as e:
                    logger.error(f"导入记忆失败: {e}")
                    await session.rollback()

                j += 2
            else:
                j += 1

    await session.commit()
    return memory_count


# ============== 检索测试 ==============

async def test_retrieval(
    session: AsyncSession,
    user_id: str,
    qa_data: QAData,
    top_k: int = 5,
    use_llm_answer: bool = False,
) -> list[TestResult]:
    """执行检索测试"""
    llm = LLMFactory.get_provider()
    retriever = MemoryRetriever(session, llm)

    results = []

    for q in qa_data.questions:
        try:
            # 执行检索
            retrieved = await retriever.retrieve(
                user_id=user_id,
                query=q.question,
                top_k=top_k,
                use_llm_classification=True,
            )

            # 提取检索结果
            contexts = []
            scores = []
            for r in retrieved:
                resource = r.get("resource")
                if resource and resource.description:
                    contexts.append(resource.description)
                    scores.append(r.get("score", 0))

            # 判断检索结果是否相关（简单关键词匹配）
            is_relevant = _check_relevance(contexts, q.answer, q.evidence)

            result = TestResult(
                question=q.question,
                expected_answer=q.answer,
                retrieved_contexts=contexts,
                retrieved_scores=scores,
                is_relevant=is_relevant,
            )

            # 可选：让 LLM 基于检索结果回答
            if use_llm_answer and contexts:
                context_text = "\n".join(contexts[:3])  # 使用前 3 个结果
                result.llm_answer = await _generate_llm_answer(llm, q.question, context_text)
                result.is_correct = _check_answer_correctness(result.llm_answer, q.answer)

            results.append(result)

        except Exception as e:
            logger.error(f"检索测试失败: {q.question} - {e}")
            results.append(TestResult(
                question=q.question,
                expected_answer=q.answer,
                retrieved_contexts=[],
                retrieved_scores=[],
                is_relevant=False,
            ))

    return results


def _check_relevance(
    contexts: list[str],
    expected_answer: str,
    evidence: list[str],
) -> bool:
    """检查检索结果是否包含相关信息

    简单实现：检查关键词是否在上下文中出现
    """
    # 提取预期答案中的关键词
    answer_keywords = set(re.findall(r"\w+", expected_answer.lower()))

    # 检查上下文是否包含关键词
    combined_context = " ".join(contexts).lower()

    # 至少有一个关键词匹配
    for keyword in answer_keywords:
        if len(keyword) >= 3 and keyword in combined_context:
            return True

    return False


async def _generate_llm_answer(
    llm,
    question: str,
    context: str,
) -> str:
    """让 LLM 基于检索结果生成回答"""
    system_prompt = """你是一个问答助手。请根据提供的上下文回答问题。
如果上下文中没有相关信息，请回答"我不知道"。回答要简洁准确。"""

    user_query = f"""上下文：
{context}

问题：{question}"""

    response = await llm.generate_chat_response(
        system_prompt=system_prompt,
        context="",
        user_query=user_query,
    )
    return response.strip()


def _check_answer_correctness(llm_answer: str, expected_answer: str) -> bool:
    """检查 LLM 回答是否正确（简单关键词匹配）"""
    llm_lower = llm_answer.lower()
    expected_keywords = set(re.findall(r"\w+", expected_answer.lower()))

    # 至少有一个关键信息匹配
    for keyword in expected_keywords:
        if len(keyword) >= 3 and keyword in llm_lower:
            return True

    return False


# ============== 报告生成 ==============

def calculate_metrics(results: list[TestResult]) -> dict[str, float]:
    """计算测试指标"""
    if not results:
        return {"recall_at_k": 0, "mrr": 0, "avg_score": 0}

    # Recall@K: 有相关结果的问题比例
    relevant_count = sum(1 for r in results if r.is_relevant)
    recall_at_k = relevant_count / len(results)

    # MRR: Mean Reciprocal Rank（简化版，使用分数排序）
    # 这里用平均检索分数代替
    avg_score = sum(sum(r.retrieved_scores) / max(len(r.retrieved_scores), 1) for r in results) / len(results)

    # LLM 回答正确率（如果启用）
    llm_correct = None
    answered_results = [r for r in results if r.is_correct is not None]
    if answered_results:
        correct_count = sum(1 for r in answered_results if r.is_correct)
        llm_correct = correct_count / len(answered_results)

    return {
        "recall_at_k": recall_at_k,
        "mrr": avg_score,  # 简化：用平均分数代替
        "avg_score": avg_score,
        "llm_correctness": llm_correct,
    }


def generate_report(report: SampleReport) -> str:
    """生成测试报告"""
    metrics = calculate_metrics(report.results)

    lines = [
        "=" * 60,
        f"测试报告 - Sample {report.sample_index} ({report.character})",
        "=" * 60,
        f"导入会话数: {report.total_sessions}",
        f"创建记忆数: {report.total_memories}",
        f"测试问题数: {report.total_questions}",
        "",
        "--- 检索指标 ---",
        f"Recall@K: {metrics['recall_at_k']:.2%}",
        f"平均检索分数: {metrics['avg_score']:.3f}",
    ]

    if metrics.get("llm_correctness") is not None:
        lines.append(f"LLM 回答正确率: {metrics['llm_correctness']:.2%}")

    lines.extend([
        "",
        "--- 详细结果 ---",
    ])

    # 显示部分结果示例
    for i, r in enumerate(report.results[:5]):
        lines.append(f"\n[{i + 1}] Q: {r.question}")
        lines.append(f"    预期: {r.expected_answer}")
        lines.append(f"    相关: {'✓' if r.is_relevant else '✗'}")
        if r.retrieved_scores:
            lines.append(f"    检索分数: {r.retrieved_scores[0]:.3f}")

    if len(report.results) > 5:
        lines.append(f"\n... 还有 {len(report.results) - 5} 个结果")

    return "\n".join(lines)


# ============== 主测试流程 ==============

async def run_single_sample(
    sample_index: int,
    import_only: bool = False,
    enable_dedup: bool = False,
    use_llm_answer: bool = False,
    top_k: int = 5,
) -> SampleReport | None:
    """运行单个 sample 的测试"""
    # 查找对应文件
    converted_files = sorted(DATA_DIR.glob(f"sample_{sample_index}_*_converted.json"))
    qa_file = DATA_DIR / f"sample_{sample_index}_qa.json"

    if not converted_files:
        logger.error(f"未找到 sample_{sample_index} 的数据文件")
        return None

    if not qa_file.exists() and not import_only:
        logger.error(f"未找到 sample_{sample_index} 的 QA 文件")
        return None

    reports = []

    async with AsyncSessionLocal() as session:
        for converted_file in converted_files:
            # 解析数据
            converted = parse_converted_file(converted_file)
            logger.info(f"加载数据: {converted_file.name} ({converted.total_sessions} sessions)")

            # 导入数据
            memory_count = await import_converted_data(session, converted, enable_dedup=enable_dedup)
            logger.info(f"导入完成: {memory_count} 条记忆")

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
            qa_filtered.total_questions = len(qa_filtered.questions)

            logger.info(f"测试 QA: {qa_filtered.total_questions} 个问题 (角色: {converted.user_character})")

            # 执行检索测试
            results = await test_retrieval(
                session,
                converted.user_id,
                qa_filtered,
                top_k=top_k,
                use_llm_answer=use_llm_answer,
            )

            # 生成报告
            report = SampleReport(
                sample_index=sample_index,
                character=converted.user_character,
                total_sessions=converted.total_sessions,
                total_memories=memory_count,
                total_questions=qa_filtered.total_questions,
                results=results,
            )
            reports.append(report)

            # 打印单个角色报告
            print(generate_report(report))

    # 返回第一个报告（如果有多个角色，可以合并）
    return reports[0] if reports else None


async def run_all_samples(
    import_only: bool = False,
    enable_dedup: bool = False,
    use_llm_answer: bool = False,
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
        report = await run_single_sample(
            idx,
            import_only=import_only,
            enable_dedup=enable_dedup,
            use_llm_answer=use_llm_answer,
        )
        if report:
            all_reports.append(report)

    # 生成总体报告
    if all_reports and not import_only:
        print("\n" + "=" * 60)
        print("总体测试报告")
        print("=" * 60)

        total_questions = sum(r.total_questions for r in all_reports)
        total_relevant = sum(sum(1 for res in r.results if res.is_relevant) for r in all_reports)

        print(f"总测试问题数: {total_questions}")
        print(f"总相关问题数: {total_relevant}")
        print(f"总体 Recall@K: {total_relevant / total_questions:.2%}" if total_questions > 0 else "N/A")


# ============== 入口 ==============

def main():
    parser = argparse.ArgumentParser(description="使用 converted_data_zh 数据集测试 Mymem 记忆系统")
    parser.add_argument("--sample", type=int, help="指定要测试的 sample index")
    parser.add_argument("--all", action="store_true", help="运行所有 sample 测试")
    parser.add_argument("--import-only", action="store_true", help="仅导入数据，不执行测试")
    parser.add_argument("--no-dedup", action="store_true", help="禁用记忆去重")
    parser.add_argument("--llm-answer", action="store_true", help="让 LLM 基于检索结果回答")
    parser.add_argument("--top-k", type=int, default=5, help="检索返回数量 (默认: 5)")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细日志")

    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # 运行测试
    if args.all:
        asyncio.run(run_all_samples(
            import_only=args.import_only,
            enable_dedup=not args.no_dedup,
            use_llm_answer=args.llm_answer,
        ))
    elif args.sample is not None:
        asyncio.run(run_single_sample(
            args.sample,
            import_only=args.import_only,
            enable_dedup=not args.no_dedup,
            use_llm_answer=args.llm_answer,
            top_k=args.top_k,
        ))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
