## 1. 总览
- 结果文件: mymem_test_results_20260425_153605.json
- 题目数: 23
- 存储覆盖率: 100.00%
- 成功写入题数: 23
- 未写入题数: 0
- 统计口径风险: 当前结果里没有额外高风险提示。

## 2. 失败原因
- 没有发现 storage_hit=False 的失败样本。

## 3. 成功模式
- 大部分题已经能在数据库里找到候选 evidence，共 23 题 storage_hit=True。
- 这说明主问题不一定在写入本身，后续应继续看 retrieval 和 answer 阶段是否正确利用了这些 evidence。

## 4. 代表性案例
- 案例1: What fields would Caroline be likely to pursue in her educaton?
  - category: Category 3 - 推理归纳（需要综合多事实）
  - standard_answer: Psychology, counseling certification
  - storage_hit=True | retrieval_hit=None | rank=None | layer=none
  - answer_support_type: profile_inference
  - diagnosis: none
  - reason: 回答正确来源更接近画像推断；这类题可以算答对，但应和直接事实召回分开看。
- 案例2: When did Caroline join a new activist group?
  - category: Category 2 - 时间相关（when/how long）
  - standard_answer: The Tuesday before 8 February 2026
  - storage_hit=True | retrieval_hit=None | rank=None | layer=none
  - answer_support_type: unsupported
  - diagnosis: none
  - reason: 回答虽然正确，但 retrieval_hit=False，说明这次成功不能直接证明检索链路有效。

## 5. 建议动作
- P0: 对 storage_hit=False 的题，回放 extraction 输出，确认事实是否在抽取阶段就丢失。
- P0: 对写入命中但 evidence 质量差的题，检查去重和 category 归类是否过粗。
- P1: 在存储报告中补充 language / time / evidence 命中统计，便于追溯污染来源。