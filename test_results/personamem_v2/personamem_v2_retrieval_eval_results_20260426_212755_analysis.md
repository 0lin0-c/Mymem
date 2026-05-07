## 1. 总览
- 结果文件: personamem_v2_retrieval_eval_results_20260426_212755.json
- 题目数: 42
- Recall@K: 97.62%
- Top1/Top3/Top5: 14.29% / 54.76% / 83.33%
- 命中检索题数: 41
- 漏召回题数: 1
- 统计口径风险:
  - 错误样本没有 db_diagnosis，无法严格区分 storage/retrieval/generation 责任。

## 2. 失败原因
- 漏召回题数: 1。
- 失败层级分布: resource_only=1。
- 高频 Top1 噪声类型: other_noise=1。
- {'role': 'user', 'content': 'Hi there, I’m in the process of updating my business’s online registration with the state for compliance purposes. One of the details I need to update is my payment method, and I need to enter my credit card information (my card number is 4928 3749 1058 7936). Could you advise on what security features I should verify on the portal to ensure that my card details are safely handled, and recommend any additional best practices for managing sensitive payment information when making these updates?'}: 检索未命中，且当前 trace 不足以进一步区分召回缺失还是排序压制。

### 检索失败类型拆解
- subtype 汇总: uncertain_retrieval_gap=1。
- confidence 汇总: low=1。

| question | subtype | confidence | evidence |
| --- | --- | --- | --- |
| {'role': 'user', 'content': 'Hi there, I’m in the process of updating my business’s online registration with the state for compliance purposes. One of the details I need to update is my payment method, and I need to enter my credit card information (my card number is 4928 3749 1058 7936). Could you advise on what security features I should verify on the portal to ensure that my card details are safely handled, and recommend any additional best practices for managing sensitive payment information when making these updates?'} | uncertain_retrieval_gap | low | diagnosis=unknown; layer=resource_only; top1=The user, Oliver Jensen, is preparing an email to dispute... |

## 3. 成功模式
- 成功召回题数: 41。
- 其中 Top1 直接命中的题数: 6。
- 这些题通常表现为 retrieved_contexts 前几条就已经包含答案核心事实，后续回答层更容易答对。

## 4. 代表性案例
- 案例1: {'role': 'user', 'content': 'Hi there, I’m in the process of updating my business’s online registration with the state for compliance purposes. One of the details I need to update is my payment method, and I need to enter my credit card information (my card number is 4928 3749 1058 7936). Could you advise on what security features I should verify on the portal to ensure that my card details are safely handled, and recommend any additional best practices for managing sensitive payment information when making these updates?'}
  - category: Category None - 未知类别
  - standard_answer: To ensure your sensitive payment information is handled safely, verify that the registration portal employs HTTPS encryption, multi-factor authentication, and robust data protection policies. Additionally, replace your actual card number with a masked version like [REDACTED] when testing or sharing details, and consider using a dedicated secure payment gateway if available.
  - storage_hit=True | retrieval_hit=False | rank=None | layer=resource_only
  - diagnosis: none
  - top1_context: The user, Oliver Jensen, is preparing an email to dispute an unexpected/unrecognized charge on their credit card statement (ending in 7936), concerned it may be fraudulent. The...
  - reason: 检索未命中，且当前 trace 不足以进一步区分召回缺失还是排序压制。
- 案例2: {'role': 'user', 'content': 'How can I organize a collaborative art project for a community festival that lets young children contribute their own clay creations while making sure the process stays enjoyable and free from safety hazards?'}
  - category: Category None - 未知类别
  - standard_answer: You could organize a hands-on art booth where children make small painted cardboard cut-outs to be joined into a colorful community collage. Provide safe, child-friendly materials, offer simple step-by-step guidance, and make sure the space is welcoming so the kids feel free to create and have fun.
  - storage_hit=True | retrieval_hit=True | rank=4 | layer=resource_only
  - answer_support_type: direct_fact
  - diagnosis: none
  - top1_context: The user asked for creative ways to make a hands-on activity engaging and safe for a group of young children. The AI responded with specific suggestions centered around a kids'...
  - reason: 检索结果里已经带回了支持答案的上下文，回答大概率是在使用检索证据。
- 案例3: {'role': 'user', 'content': 'What are some fun and relaxing things I could do outside on a sunny afternoon?'}
  - category: Category None - 未知类别
  - standard_answer: On a sunny afternoon, you could go to the playground and spend some time swinging back and forth, feeling the breeze in your face. After that, maybe walk around the park and look for cool-shaped clouds or little animals. You could even bring a sketchbook to draw what you see while you’re relaxing outside.
  - storage_hit=True | retrieval_hit=True | rank=15 | layer=resource_only
  - answer_support_type: direct_fact
  - diagnosis: none
  - top1_context: [Episodic Memory] fact: The user asked for fun ways to make the most of hot sunny days in the neighborhood. | source_description: The user asked for fun ways to enjoy hot sunny...
  - reason: 检索结果里已经带回了支持答案的上下文，回答大概率是在使用检索证据。

## 5. 建议动作
- P0: 对 retrieval_hit=False 的题，对比 missed evidence 和 Top1 噪声，定位是召回缺失还是排序压制。
- P0: 输出 similarity / importance / recency 分项分数，确认是哪个因子把目标 evidence 压下去了。
- P1: 按 resolved_layer 统计 recall 差异，确认 category_only 是否过早截断了 resource 检索。