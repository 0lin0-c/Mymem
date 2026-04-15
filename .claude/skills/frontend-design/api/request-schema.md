# 前端请求契约

本文档定义前端提交至后端的完整请求结构。

---

## 请求示例

提交至后端 API：`POST /v1/user/onboarding`

```json
{
  "username": "小明",
  "identity_type": "student",
  "identity_detail": {
    "education_stage": "high",
    "major": "计算机科学"
  },
  "use_cases": ["学习辅助", "创意灵感"],
  "interests": ["文学", "电影"],
  "ai_customization": {
    "ai_name": "小智",
    "ai_role": "mentor",
    "personality": ["温柔耐心", "严谨专业"],
    "communication_style": "daily"
  }
}
```

---

## 字段说明

### 顶层字段

| 字段 | 类型 | 必填 | 说明 | 校验规则 |
|------|------|------|------|----------|
| `username` | string | 是 | 用户名称 | 1-50 字符 |
| `identity_type` | enum | 是 | 身份类型 | `student` / `worker` / `teacher` / `freelancer` / `other` |
| `identity_detail` | object | 否 | 身份详情，结构根据 `identity_type` 变化 | 见下方详情 |
| `use_cases` | string[] | 否 | 使用场景（多选） | 直接提交中文 |
| `interests` | string[] | 否 | 兴趣标签（多选） | 直接提交中文 |
| `ai_customization` | object | 是 | AI 助手定制配置 | 见下方详情 |

---

### identity_detail 结构

根据 `identity_type` 不同，`identity_detail` 包含不同字段：

#### identity_type = "student"

```json
{
  "education_stage": "high",    // 可选: elementary/middle/high/college/graduate
  "major": "计算机科学"          // 可选: 专业方向
}
```

#### identity_type = "worker"

```json
{
  "industry": "互联网",          // 可选: 所在行业
  "job_title": "工程师"          // 可选: 职位名称
}
```

#### identity_type = "teacher"

```json
{
  "subject": "数学",             // 可选: 任教学科
  "teaching_stage": "高中"       // 可选: 教学学段
}
```

#### identity_type = "freelancer"

```json
{
  "field": "独立开发"            // 可选: 从事领域
}
```

#### identity_type = "other"

```json
{
  "description": "退休人员"      // 可选: 自定义身份描述
}
```

---

### ai_customization 结构

| 字段 | 类型 | 必填 | 说明 | 校验规则 |
|------|------|------|------|----------|
| `ai_name` | string | 是 | AI 助手名字 | 1-20 字符 |
| `ai_role` | enum | 是 | AI 角色 | `assistant` / `mentor` / `friend` / `advisor` / `partner` |
| `personality` | string[] | 否 | AI 性格特点（多选，无上限） | 直接提交中文 |
| `communication_style` | enum | 否 | 沟通风格，默认 `daily` | `formal` / `casual` / `academic` / `daily` |

---

## 枚举值汇总

### identity_type

| 提交值 | 中文显示 |
|--------|----------|
| `student` | 学生 |
| `worker` | 上班族 |
| `teacher` | 教师 |
| `freelancer` | 自由职业者 |
| `other` | 其他 |

### education_stage

| 提交值 | 中文显示 |
|--------|----------|
| `elementary` | 小学 |
| `middle` | 初中 |
| `high` | 高中 |
| `college` | 大学 |
| `graduate` | 研究生 |

### ai_role

| 提交值 | 中文显示 |
|--------|----------|
| `assistant` | 助手 |
| `mentor` | 导师 |
| `friend` | 朋友 |
| `advisor` | 顾问 |
| `partner` | 伙伴 |

### communication_style

| 提交值 | 中文显示 |
|--------|----------|
| `formal` | 正式严谨 |
| `casual` | 轻松随意 |
| `academic` | 学术专业 |
| `daily` | 日常轻松 |

---

## 校验错误提示

| 字段 | 错误场景 | 提示文案 |
|------|----------|----------|
| `username` | 为空 | 请输入您的昵称 |
| `username` | 超长 | 昵称最多 50 个字符 |
| `identity_type` | 未选择 | 请选择您的身份类型 |
| `ai_name` | 为空 | 请给 AI 助手起个名字 |
| `ai_name` | 超长 | 名字最多 20 个字符 |
| `ai_role` | 未选择 | 请选择 AI 助手的身份 |
