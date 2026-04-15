# 📋 Mymem 扩展方案总览

本文档汇总了 Mymem 项目的两个主要扩展方向，提供实施路线图。

---

## 扩展一：检索效果评测方案

**文档**: [RETRIEVAL_BENCHMARK.md](./RETRIEVAL_BENCHMARK.md)

### 核心目标

将检索系统从"逻辑正确"提升到"效果优化"，通过数据集跑分量化评估检索质量。

### 关键指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| Hit Rate@5 | Top5 包含正确答案的比例 | > 80% |
| MRR | 平均倒数排名 | > 0.6 |
| NDCG@5 | 排序质量 | > 0.7 |

### 实施步骤

```
Week 1: 基础设施
├── 创建 evaluation/ 目录
├── 实现 metrics.py 指标计算
└── 实现 dataset_loader.py

Week 2: 评测流程
├── 实现 benchmark.py 主流程
├── 数据注入与跑分
└── 报告生成

Week 3+: 调优迭代
├── 参数消融实验
├── 记录最优配置
└── 持续优化
```

---

## 扩展二：Agent 能力集成

**文档**: [AGENT_INTEGRATION.md](./AGENT_INTEGRATION.md)

### 核心目标

为记忆系统"装上手脚"，使其具备操作电脑的能力，进化为真正的智能 Agent。

### 架构设计

```
┌───────────────────────────────────────────────┐
│                 Mymem Agent                   │
├───────────────────────────────────────────────┤
│  Memory Layer ←→ Agent Core ←→ Tool Layer    │
│  (已有)         (新增)        (新增)          │
└───────────────────────────────────────────────┘
```

### 工具清单

| 类别 | 工具 | 优先级 |
|------|------|--------|
| 文件操作 | read, write, list | P0 |
| 代码执行 | python_exec | P0 |
| 网络 | web_search, web_fetch | P1 |
| 系统 | process_list | P2 |

### 实施步骤

```
Week 1-2: 工具层
├── 创建 services/tools/ 目录
├── 实现 BaseTool 抽象基类
├── 实现文件操作工具
└── 实现 ToolRegistry

Week 2-3: Agent 核心
├── 创建 services/agent/ 目录
├── 实现 AgentCore 控制循环
├── 集成记忆系统
└── 实现安全沙箱

Week 3-4: API 与集成
├── Agent API 路由
├── 与 Chat API 集成
└── 端到端测试
```

---

## 两者的协同效应

| 场景 | 检索评测 | Agent 能力 |
|------|----------|------------|
| **执行记录存储** | 评测如何存储记忆 | Agent 执行结果自动存入记忆 |
| **上下文检索** | 评测检索效果 | Agent 执行前检索相关记忆 |
| **效果评估** | 量化指标 | 可评估 Agent 任务完成率 |
| **持续学习** | 调优检索参数 | Agent 从历史经验学习 |

---

## 实施优先级建议

### 高优先级 (P0)

1. **工具层基础** - 文件操作工具是 Agent 的基础能力
2. **评测基础设施** - 没有量化指标就无法判断优化效果

### 中优先级 (P1)

1. **Agent 核心** - 依赖工具层完成
2. **调优迭代** - 依赖评测基础设施

### 低优先级 (P2)

1. **扩展工具** - 网络操作、系统操作
2. **多 Agent 协作** - 进阶功能

---

## 开发时间线

```
           Week 1        Week 2        Week 3        Week 4
         ┌───────────┬───────────┬───────────┬───────────┐
评测方案 │ ████████  │ ████████  │ ░░░░░░░░  │ ░░░░░░░░  │
         │ 基础设施  │ 评测流程  │           │           │
         ├───────────┼───────────┼───────────┼───────────┤
Agent    │ ████████  │ ████████  │ ████████  │ ░░░░░░░░  │
集成     │ 工具层    │ Agent核心 │ API集成   │           │
         └───────────┴───────────┴───────────┴───────────┘
```

---

## 新增文件清单

```
Mymem/
├── evaluation/                 # 检索评测模块
│   ├── __init__.py
│   ├── benchmark.py
│   ├── metrics.py
│   ├── dataset_loader.py
│   └── reporter.py
│
├── services/
│   ├── agent/                  # Agent 核心模块
│   │   ├── __init__.py
│   │   ├── core.py
│   │   └── state.py
│   │
│   └── tools/                  # 工具层模块
│       ├── __init__.py
│       ├── base.py
│       ├── registry.py
│       ├── file_tools.py
│       ├── code_tools.py
│       └── sandbox.py
│
├── api/v1/
│   └── agent.py                # Agent API
│
├── schemas/
│   └── agent_schema.py         # Agent Schema
│
└── docs/
    ├── RETRIEVAL_BENCHMARK.md  # 评测方案文档
    ├── AGENT_INTEGRATION.md    # Agent 集成文档
    └── UPGRADE_ROADMAP.md      # 本文档
```

---

## 开始实施

建议按以下顺序开始：

1. **阅读详细文档**
   - [RETRIEVAL_BENCHMARK.md](./RETRIEVAL_BENCHMARK.md) - 评测方案
   - [AGENT_INTEGRATION.md](./AGENT_INTEGRATION.md) - Agent 集成

2. **选择起点**
   - 优先完成评测基础设施 → 后续调优有数据支撑
   - 或者优先完成工具层 → 快速看到 Agent 效果

3. **联系开发**
   - 告诉我你想先做哪个，我会帮你逐步实现代码
