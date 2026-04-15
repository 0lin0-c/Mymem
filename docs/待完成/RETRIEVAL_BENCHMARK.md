# 🎯 检索效果评测方案

## 1. 背景与目标

当前 `tests/` 目录下的测试主要验证代码逻辑正确性，无法评估检索的实际效果。本方案引入**数据集跑分机制**，量化评估检索质量，为调优提供数据支撑。

### 评测目标

| 维度 | 说明 | 指标 |
|------|------|------|
| **准确率** | 返回结果是否包含正确答案 | Hit Rate@K |
| **召回率** | 正确答案是否被检索到 | Recall@K |
| **排序质量** | 正确答案在结果中的位置 | MRR, NDCG |
| **分类准确性** | LLM 分类判断是否正确 | Category F1 |

---

## 2. 数据集设计

### 2.1 使用 LoCoMo 数据集

已有的 `data/locomo10.json` 是 LoCoMo 数据集的一个子集，包含：

```json
{
  "qa": [
    {
      "question": "When did Caroline go to the LGBTQ support group?",
      "answer": "7 May 2023",
      "evidence": ["D1:3"],
      "category": 2
    }
  ],
  "documents": [
    {
      "id": "D1",
      "content": "对话内容..."
    }
  ]
}
```

**数据结构说明**：
- `qa`: 问答对，`evidence` 指向支撑答案的文档片段
- `documents`: 原始对话/记忆文档
- `category`: 问题类型（1=事实型，2=时间型，3=推理型）

### 2.2 数据注入流程

```
LoCoMo JSON
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. 解析 documents → 转为 User Chat      │
│    每个 document 模拟一个用户的对话历史  │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ 2. 调用 MemoryWriter.save_chat()        │
│    落库到 resources + categories        │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ 3. 执行 qa 问答测试                     │
│    question → retrieve() → 评估结果     │
└─────────────────────────────────────────┘
```

---

## 3. 评测指标详解

### 3.1 Hit Rate@K

正确答案出现在 Top-K 结果中的比例。

```python
def hit_rate_at_k(results: list, ground_truth: str, k: int) -> int:
    """
    Hit Rate@K: 1 if ground_truth in top-k, else 0
    """
    top_k_contents = [r["resource"].description for r in results[:k]]
    return 1 if any(ground_truth in content for content in top_k_contents) else 0
```

### 3.2 Mean Reciprocal Rank (MRR)

正确答案在结果列表中的排名倒数的均值。

```python
def mrr(results: list, ground_truth: str) -> float:
    """
    MRR: 1/rank of first relevant result
    """
    for i, r in enumerate(results, 1):
        if ground_truth in r["resource"].description:
            return 1.0 / i
    return 0.0
```

### 3.3 NDCG@K (Normalized Discounted Cumulative Gain)

考虑排序位置的加权指标。

```python
import math

def dcg_at_k(relevances: list[int], k: int) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(relevances[:k]))

def ndcg_at_k(results: list, ground_truths: list[str], k: int) -> float:
    relevances = [1 if any(gt in r["resource"].description for gt in ground_truths) else 0
                  for r in results[:k]]
    ideal = sorted(relevances, reverse=True)

    dcg = dcg_at_k(relevances, k)
    idcg = dcg_at_k(ideal, k)

    return dcg / idcg if idcg > 0 else 0.0
```

### 3.4 Category Classification F1

评估 LLM 分类判断的准确性。

```python
from sklearn.metrics import f1_score

def category_f1(predicted: list[str], actual: list[str]) -> float:
    """
    计算分类预测的 F1 分数
    """
    # 转为多标签格式
    all_categories = list(set(predicted + actual))
    y_pred = [1 if c in predicted else 0 for c in all_categories]
    y_true = [1 if c in actual else 0 for c in all_categories]

    return f1_score(y_true, y_pred)
```

---

## 4. 评测实现

### 4.1 目录结构

```
Mymem/
├── evaluation/                 # 新增评测模块
│   ├── __init__.py
│   ├── benchmark.py            # 评测主流程
│   ├── metrics.py              # 指标计算函数
│   ├── dataset_loader.py       # 数据集加载器
│   ├── reporter.py             # 结果报告生成
│   └── configs/
│       └── default.yaml        # 评测配置
│
├── data/
│   ├── locomo10.json           # 已有数据集
│   └── custom/                 # 自定义测试数据
│
└── tests/
    └── test_evaluation/        # 评测测试
        └── test_benchmark.py
```

### 4.2 核心代码：benchmark.py

```python
# evaluation/benchmark.py
import asyncio
import logging
from typing import List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from services.retrieval.retriever import MemoryRetriever
from services.memory.writer import MemoryWriter
from services.llm.base import BaseLLMProvider
from evaluation.metrics import (
    hit_rate_at_k,
    mrr,
    ndcg_at_k,
    category_f1,
)

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    """单个问题的评测结果"""
    question: str
    ground_truth: str
    predicted: List[str]
    hit_1: int
    hit_3: int
    hit_5: int
    mrr_score: float
    ndcg_5: float
    category_f1: float
    retrieval_time_ms: float


@dataclass
class BenchmarkReport:
    """完整评测报告"""
    dataset_name: str
    total_questions: int
    avg_hit_rate_1: float
    avg_hit_rate_3: float
    avg_hit_rate_5: float
    avg_mrr: float
    avg_ndcg_5: float
    avg_category_f1: float
    avg_retrieval_time_ms: float
    results: List[EvalResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class RetrievalBenchmark:
    """检索效果评测器"""

    def __init__(
        self,
        session: AsyncSession,
        llm: BaseLLMProvider,
        top_k: int = 5,
    ):
        self.session = session
        self.llm = llm
        self.top_k = top_k
        self.retriever = MemoryRetriever(session, llm)
        self.writer = MemoryWriter(session, llm)

    async def load_dataset(self, dataset_path: str) -> Dict[str, Any]:
        """加载数据集"""
        import json
        with open(dataset_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def ingest_documents(
        self,
        documents: List[Dict],
        user_id: str,
    ) -> None:
        """将数据集文档注入记忆系统"""
        for doc in documents:
            # 将文档内容转为对话形式
            await self.writer.save_chat(
                user_id=user_id,
                user_input=doc.get("content", ""),
                assistant_response="[Document imported for evaluation]",
                modality="text",
            )
        await self.session.commit()
        logger.info(f"Ingested {len(documents)} documents for user {user_id}")

    async def evaluate_single(
        self,
        question: str,
        ground_truth: str,
        evidence_ids: List[str],
        user_id: str,
    ) -> EvalResult:
        """评估单个问题"""
        import time

        start_time = time.time()

        # 执行检索
        results = await self.retriever.retrieve(
            user_id=user_id,
            query=question,
            top_k=self.top_k,
        )

        retrieval_time = (time.time() - start_time) * 1000

        # 计算指标
        predicted = [r["resource"].description for r in results]

        return EvalResult(
            question=question,
            ground_truth=ground_truth,
            predicted=predicted,
            hit_1=hit_rate_at_k(results, ground_truth, k=1),
            hit_3=hit_rate_at_k(results, ground_truth, k=3),
            hit_5=hit_rate_at_k(results, ground_truth, k=5),
            mrr_score=mrr(results, ground_truth),
            ndcg_5=ndcg_at_k(results, [ground_truth], k=5),
            category_f1=0.0,  # 需要实际分类标签
            retrieval_time_ms=retrieval_time,
        )

    async def run_benchmark(
        self,
        dataset_path: str,
        user_id: str,
    ) -> BenchmarkReport:
        """运行完整评测"""
        import time

        # 加载数据集
        dataset = await self.load_dataset(dataset_path)
        documents = dataset.get("documents", [])
        qa_pairs = dataset.get("qa", [])

        # 注入文档
        logger.info(f"Loading {len(documents)} documents...")
        await self.ingest_documents(documents, user_id)

        # 评估每个问题
        results = []
        for qa in qa_pairs:
            eval_result = await self.evaluate_single(
                question=qa["question"],
                ground_truth=qa["answer"],
                evidence_ids=qa.get("evidence", []),
                user_id=user_id,
            )
            results.append(eval_result)
            logger.info(f"Q: {qa['question'][:50]}... Hit@5={eval_result.hit_5}")

        # 计算平均指标
        n = len(results)
        report = BenchmarkReport(
            dataset_name=dataset_path,
            total_questions=n,
            avg_hit_rate_1=sum(r.hit_1 for r in results) / n,
            avg_hit_rate_3=sum(r.hit_3 for r in results) / n,
            avg_hit_rate_5=sum(r.hit_5 for r in results) / n,
            avg_mrr=sum(r.mrr_score for r in results) / n,
            avg_ndcg_5=sum(r.ndcg_5 for r in results) / n,
            avg_category_f1=sum(r.category_f1 for r in results) / n,
            avg_retrieval_time_ms=sum(r.retrieval_time_ms for r in results) / n,
            results=results,
        )

        return report

    def print_report(self, report: BenchmarkReport) -> None:
        """打印评测报告"""
        print("\n" + "=" * 60)
        print(f"📊 Retrieval Benchmark Report")
        print("=" * 60)
        print(f"Dataset: {report.dataset_name}")
        print(f"Total Questions: {report.total_questions}")
        print("-" * 60)
        print(f"Hit Rate@1:  {report.avg_hit_rate_1:.2%}")
        print(f"Hit Rate@3:  {report.avg_hit_rate_3:.2%}")
        print(f"Hit Rate@5:  {report.avg_hit_rate_5:.2%}")
        print(f"MRR:         {report.avg_mrr:.4f}")
        print(f"NDCG@5:      {report.avg_ndcg_5:.4f}")
        print(f"Category F1: {report.avg_category_f1:.4f}")
        print(f"Avg Time:    {report.avg_retrieval_time_ms:.2f}ms")
        print("=" * 60 + "\n")
```

### 4.3 运行评测

```bash
# 命令行入口
python -m evaluation.benchmark --dataset data/locomo10.json --output reports/benchmark_20240402.json
```

---

## 5. 调优策略

### 5.1 参数调优维度

| 参数 | 当前值 | 调优方向 | 影响 |
|------|--------|----------|------|
| `similarity_weight` | 0.6 | 0.4-0.8 | 向量相似度权重 |
| `importance_weight` | 0.4 | 0.2-0.6 | 重要性权重 |
| `min_importance` | 3 | 1-5 | 最低重要性阈值 |
| `similarity_threshold` | 0.55 | 0.4-0.7 | 相似度过滤阈值 |
| `llm_classification` | True | True/False | 是否启用 LLM 分类 |

### 5.2 消融实验设计

```python
# 消融实验配置
ABLATION_CONFIGS = [
    {"name": "baseline", "similarity_weight": 0.6, "use_llm_classification": True},
    {"name": "no_llm_class", "similarity_weight": 0.6, "use_llm_classification": False},
    {"name": "high_sim_weight", "similarity_weight": 0.8, "use_llm_classification": True},
    {"name": "high_imp_weight", "similarity_weight": 0.4, "use_llm_classification": True},
]
```

### 5.3 调优流程

```
1. 运行 baseline 评测
       ↓
2. 记录各项指标
       ↓
3. 调整单个参数
       ↓
4. 重新评测并对比
       ↓
5. 选择最优配置
```

---

## 6. 实现步骤

### Phase 1：基础设施（1-2 天）

1. [ ] 创建 `evaluation/` 目录结构
2. [ ] 实现 `metrics.py` 指标计算函数
3. [ ] 实现 `dataset_loader.py` 数据加载器
4. [ ] 编写单元测试

### Phase 2：评测流程（2-3 天）

1. [ ] 实现 `benchmark.py` 主流程
2. [ ] 实现数据注入逻辑
3. [ ] 实现结果报告生成
4. [ ] 命令行入口

### Phase 3：调优迭代（持续）

1. [ ] 运行 baseline 评测
2. [ ] 执行消融实验
3. [ ] 分析结果并调优
4. [ ] 记录最优配置

---

## 7. 预期产出

| 产出物 | 说明 |
|--------|------|
| `evaluation/benchmark.py` | 评测主程序 |
| `evaluation/metrics.py` | 指标计算函数 |
| `reports/benchmark_*.json` | 评测报告 |
| `docs/RETRIEVAL_TUNING.md` | 调优记录文档 |

---

## 8. 扩展方向

1. **更多数据集**：支持 LoCoMo 完整版、自定义数据集
2. **A/B 测试**：对比不同检索策略
3. **在线评估**：收集用户反馈（点赞/点踩）
4. **可视化看板**：Grafana 展示评测趋势
