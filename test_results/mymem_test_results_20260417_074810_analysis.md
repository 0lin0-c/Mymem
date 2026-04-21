## 一、准确率表现拆解
- 结果文件：mymem_test_results_20260417_074810.json
- 总体准确率：33.33%（30/90）
- 剔除空标准答案后的准确率：6.25%（4/64）
- 评估样本数：90 / 总题数：90
- 检索层级准确率：
- category_only: 15 题，正确 0 题，准确率 0.0%
- category+resource: 73 题，正确 29 题，准确率 39.7%
- resource_only: 2 题，正确 1 题，准确率 50.0%
- Category 准确率：
- category 2: 19 题，正确 0 题，准确率 0.0%
- category 3: 7 题，正确 0 题，准确率 0.0%
- category 1: 13 题，正确 0 题，准确率 0.0%
- category 4: 24 题，正确 4 题，准确率 16.7%
- category 5: 27 题，正确 26 题，准确率 96.3%
- 统计口径风险：
- 存在标准答案为空但模型回答“不知道”被判正确的样本，整体准确率可能被抬高。
- 错误样本没有 db_diagnosis，无法支撑 storage/retrieval/generation 三分法深挖。

## 二、低准确率根因分析（重点）
- 错误答案模式分布：
- answer_abstained: 49 题
- category_only_false_sufficient: 5 题
- temporal_pollution_2026: 3 题
- wrong_specific_answer: 3 题
- category_only 是最高风险路径：只要充足性判断过早放行，系统就不会进入 Resource 层，导致“有粗粒度摘要但缺关键事实”的问题被放大。
- 时间类问题表现尤其差：多个 2023 年标准答案被 2026 年记忆污染，说明历史导入、去重更新或检索排序中的时间约束没有被评估报告显式追踪。
- category 5 的高准确率需要谨慎解读：存在标准答案为空且模型回答“不知道”被判正确的样本，这类题对真实记忆能力贡献有限。
- 代表性案例：
- 案例1（Caroline）: Q=How long has Caroline had her current group of friends for? | 标准=4 years | 生成=I don't have enough information to answer this question. | 层级=category+resource | category=2 | 模式=answer_abstained | Top1=Caroline于2026年4月14日（上周二）加入了一个新的LGBTQ维权活动小组
- 案例2（Caroline）: Q=When did Caroline go to the LGBTQ support group? | 标准=7 May 2023 | 生成=I don't have enough information to answer this question. | 层级=category_only | category=2 | 模式=answer_abstained | Top1=Caroline于2026年4月14日（上周二）加入了一个新的LGBTQ维权活动小组
- 案例3（Caroline）: Q=What country is Caroline's grandma from? | 标准=Sweden | 生成=I don't have enough information to answer this question. | 层级=resource_only | category=4 | 模式=answer_abstained | Top1=Caroline expressed deep gratitude for her support system, crediting their love and encouragement with helping her accept
- 案例4（Caroline）: Q=What are Caroline's plans for the summer? | 标准=researching adoption agencies | 生成=I don't have enough information to answer this question. | 层级=category+resource | category=4 | 模式=answer_abstained | Top1=Caroline is organizing an LGBTQ art show in May 2026 and will exhibit her own paintings at the event.
- 案例5（Caroline）: Q=What did Caroline research? | 标准=Adoption agencies | 生成=I don't have enough information to answer this question. | 层级=category_only | category=1 | 模式=answer_abstained | Top1=Caroline 是一位绘画艺术家，创作与跨性别身份相关的艺术作品
- 案例6（Caroline）: Q=What fields would Caroline be likely to pursue in her educaton? | 标准=Psychology, counseling certification | 生成=I don't have enough information to answer this question. | 层级=category_only | category=3 | 模式=answer_abstained | Top1=Caroline's name is Caroline
- 案例7（Caroline）: Q=Did Caroline make the black and white bowl in the photo? | 标准=No | 生成=I don't have enough information to answer this question. | 层级=category+resource | category=5 | 模式=answer_abstained | Top1=Caroline expressed deep gratitude for her support system, crediting their love and encouragement with helping her accept
- 案例8（Caroline）: Q=What is Caroline's identity? | 标准=Transgender woman | 生成=Based on the retrieved memories, Caroline's identity is a painting artist. Addit | 层级=category_only | category=1 | 模式=category_only_false_sufficient | Top1=Caroline 是一位绘画艺术家，创作与跨性别身份相关的艺术作品
- 案例9（Caroline）: Q=When did Caroline go to the adoption meeting? | 标准=The friday before 15 July 2023 | 生成=2023-07-07 (last Friday). | 层级=category+resource | category=2 | 模式=temporal_pollution_2026 | Top1=Caroline contacted the AI (addressed as Melanie) to share a major life update: during the week of April 10–16, 2026, she
- 案例10（Caroline）: Q=What are some changes Caroline has faced during her transition journey? | 标准=Changes to her body, losing unsupportive friends | 生成=During her transition journey, Caroline faced struggles and a period of personal | 层级=category+resource | category=1 | 模式=wrong_specific_answer | Top1=Caroline expressed deep gratitude for her support system, crediting their love and encouragement with helping her accept

## 三、DB 深挖结论
- 当前结果文件中带 db_diagnosis 的 QA 数：0
- DB 归因计数：{"missing": 60}
- 这份结果不能支撑“存储缺失 / DB 有但未召回 / 已召回但生成失败”的严格三分法，因为错误样本没有落盘 db_diagnosis。
- 需要补采字段：diagnosis_type、keywords、db_hits、matched_in_retrieved、missed_in_retrieval、llm_verification。
- 从已落盘字段只能做弱判断：Top context 经常与标准答案主题相邻但缺少精确事实，说明至少存在检索排序和摘要表征不足；是否属于存储缺失，需要重新跑带 db_diagnosis 的测试确认。

## 四、可执行改进路线图
- 数据处理层：导入时保留 session_date、evidence id、speaker、turn index，并把相对时间解析结果写入 Resource/Category 元数据；预期收益是时间题可回放、可定位；验证方式是 category 2 准确率和时间污染样本数。
- 检索算法层：把充足性判断从“优先足够”改为“精确事实题默认下钻 Resource”，尤其 when/where/how long/what exact 类问题；预期收益是降低 category_only 误放行；验证方式是 category_only 错误率下降。
- 排序层：加入时间一致性特征，查询/标准上下文涉及 2023 时惩罚 2026 记忆，或按 session_date 召回候选；预期收益是减少跨年份错召回；验证方式是 temporal_pollution_2026 计数下降。
- 评估层：将空标准答案题单独统计，不计入主准确率或至少给出 adjusted accuracy；预期收益是避免被“答不上来”题抬高指标；验证方式是报告同时输出 raw/adjusted accuracy。
- DB 诊断层：确保 live writer 写入 db_diagnosis，并在分析中聚合 storage_gap/retrieval_gap/generation_or_eval_gap；预期收益是从现象分析升级为链路归因；验证方式是 db_diagnosis_present_count 等于错误题数。

## 五、优先级行动清单
- P0：重新跑一次测试，确认每个错误样本都写入 db_diagnosis。
- P0：把 LiveResultWriter 的 statistics 补齐 layer_distribution/category_accuracy，避免分析拿到 `{}`。
- P0：对 category_only 错误样本回放 _check_sufficiency，检查为什么缺精确答案仍被判 sufficient。
- P0：把空标准答案样本从主准确率中剥离，输出 adjusted accuracy。
- P1：为时间题增加 session_date/evidence 命中统计，定位 2023/2026 混召回来源。
- P1：对 category 1/2/3 分别抽样检查 Resource 是否存储了标准答案关键事实。
- P1：增加 Resource 下钻兜底策略：Category 命中但答案生成 abstain 时自动二次 Resource 检索。
- P2：把 bad case 选择改为按层级、类别、错误模式分层抽样，避免报告只看前 12 题。