# PersonaMem-v2 Storage Granularity Review Draft

## GLM-5.1

- resources: 57
- categories: 315
- links: 446
- category_distribution: `{'Episodic Memory': 122, 'Core Self': 99, 'Knowledge Base': 37, 'Social Graph': 57}`
- bucket_resource_counts: `{'therapy_background': 21, 'ask_to_forget': 14, 'sensitive_info': 8, 'quoted_personal_fact': 9, 'third_person_narrative': 2, 'ordinary_preference': 2, 'low_value_task_shell': 1}`
- bucket_category_counts: `{'therapy_background': 171, 'ask_to_forget': 84, 'sensitive_info': 87, 'quoted_personal_fact': 84, 'third_person_narrative': 13, 'ordinary_preference': 4, 'low_value_task_shell': 3}`
- low_value_over_extracted_resources: 1
- high_value_resources_without_category: 1
- suspicious_misattribution_resources: 0
- sensitive_raw_mention_resources: 4

## DeepSeek-V4-Pro

- resources: 59
- categories: 314
- links: 418
- category_distribution: `{'Core Self': 75, 'Episodic Memory': 145, 'Knowledge Base': 39, 'Social Graph': 55}`
- bucket_resource_counts: `{'therapy_background': 22, 'ask_to_forget': 14, 'sensitive_info': 8, 'third_person_narrative': 2, 'quoted_personal_fact': 9, 'low_value_task_shell': 2, 'ordinary_preference': 2}`
- bucket_category_counts: `{'therapy_background': 178, 'ask_to_forget': 67, 'sensitive_info': 93, 'third_person_narrative': 9, 'quoted_personal_fact': 67, 'low_value_task_shell': 1, 'ordinary_preference': 3}`
- low_value_over_extracted_resources: 1
- high_value_resources_without_category: 1
- suspicious_misattribution_resources: 0
- sensitive_raw_mention_resources: 2

## Qwen3.5-Plus

- resources: 60
- categories: 296
- links: 432
- category_distribution: `{'Social Graph': 41, 'Episodic Memory': 158, 'Core Self': 73, 'Knowledge Base': 24}`
- bucket_resource_counts: `{'ask_to_forget': 14, 'therapy_background': 21, 'sensitive_info': 9, 'third_person_narrative': 2, 'quoted_personal_fact': 10, 'ordinary_preference': 2, 'low_value_task_shell': 2}`
- bucket_category_counts: `{'ask_to_forget': 65, 'therapy_background': 186, 'sensitive_info': 99, 'third_person_narrative': 10, 'quoted_personal_fact': 72, 'ordinary_preference': 0, 'low_value_task_shell': 0}`
- low_value_over_extracted_resources: 0
- high_value_resources_without_category: 9
- suspicious_misattribution_resources: 0
- sensitive_raw_mention_resources: 3

## GLM-5-Turbo

- resources: 59
- categories: 258
- links: 356
- category_distribution: `{'Core Self': 64, 'Episodic Memory': 131, 'Social Graph': 47, 'Knowledge Base': 16}`
- bucket_resource_counts: `{'ask_to_forget': 14, 'therapy_background': 21, 'sensitive_info': 9, 'third_person_narrative': 2, 'quoted_personal_fact': 9, 'ordinary_preference': 2, 'low_value_task_shell': 2}`
- bucket_category_counts: `{'ask_to_forget': 62, 'therapy_background': 141, 'sensitive_info': 85, 'third_person_narrative': 9, 'quoted_personal_fact': 54, 'ordinary_preference': 5, 'low_value_task_shell': 0}`
- low_value_over_extracted_resources: 0
- high_value_resources_without_category: 5
- suspicious_misattribution_resources: 0
- sensitive_raw_mention_resources: 2
