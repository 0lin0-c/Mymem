// 初始化页面逻辑
document.addEventListener('DOMContentLoaded', function () {
    const page = location.pathname.split('/').pop().replace('.html', '') || 'index';

    if (page === 'register') {
        initOnboardingPage();
    } else if (page === 'chat') {
        initChatPage();
    } else if (page === 'index' || page === '') {
        initLoginPage();
    } else if (page === 'settings') {
        initSettingsPage();
    }
});

// ========== 设置页面 ==========
function initSettingsPage() {
    const userId = localStorage.getItem('userId');
    if (!userId) {
        // 未登录，显示提示
        document.getElementById('llmSettingsForm').innerHTML = `
            <div class="not-logged-in">
                <p>请先登录后再配置 LLM</p>
                <a href="login.html" class="btn-primary btn-full">去登录</a>
            </div>
        `;
        return;
    }

    const form = document.getElementById('llmSettingsForm');
    const warmingUp = document.getElementById('warming_up');
    const successMsg = document.getElementById('success_msg');

    // 根据提供商自动填充常用 URL
    const providerSelect = document.getElementById('llm_provider');
    const baseUrlInput = document.getElementById('llm_base_url');
    const modelInput = document.getElementById('llm_model');

    const defaultUrls = {
        'openai': 'https://api.openai.com/v1',
        'deepseek': 'https://api.deepseek.com/v1',
        'qwen': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'glm': 'https://open.bigmodel.cn/api/paas/v4',
        'anthropic': '',
        'custom': '',
    };

    const defaultModels = {
        'openai': 'gpt-4o',
        'deepseek': 'deepseek-chat',
        'qwen': 'qwen-plus',
        'glm': 'glm-4',
        'anthropic': 'claude-sonnet-4-20250514',
        'custom': '',
    };

    providerSelect.addEventListener('change', function() {
        const provider = this.value;
        baseUrlInput.placeholder = defaultUrls[provider] || '请输入 API Base URL';
        modelInput.placeholder = defaultModels[provider] || '请输入模型名称';
    });

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const provider = providerSelect.value;
        const baseUrl = baseUrlInput.value.trim();
        const apiKey = document.getElementById('llm_api_key').value.trim();
        const model = modelInput.value.trim();

        // 校验
        document.querySelectorAll('.error-msg').forEach(el => el.textContent = '');

        if (!apiKey) {
            showError('llm_api_key', '请输入 API Key');
            return;
        }
        if (!model) {
            showError('llm_model', '请输入模型名称');
            return;
        }

        // 显示预热中
        form.classList.add('hidden');
        warmingUp.classList.remove('hidden');

        try {
            const result = await api.updateLLMSettings({
                user_id: userId,
                llm_provider: provider,
                llm_api_key: apiKey,
                llm_base_url: baseUrl || null,
                llm_model: model,
            });

            if (result.success) {
                // 等待预热完成（轮询状态）
                let attempts = 0;
                const maxAttempts = 30; // 最多等待 30 秒

                const checkWarmup = async () => {
                    attempts++;
                    const status = await api.getLLMSettings(userId);

                    if (status.warmed_up) {
                        warmingUp.classList.add('hidden');
                        successMsg.classList.remove('hidden');
                    } else if (attempts < maxAttempts) {
                        setTimeout(checkWarmup, 1000);
                    } else {
                        warmingUp.classList.add('hidden');
                        form.classList.remove('hidden');
                        alert('预热超时，请检查配置后重试');
                    }
                };

                setTimeout(checkWarmup, 1000);
            } else {
                warmingUp.classList.add('hidden');
                form.classList.remove('hidden');
                alert('保存失败：' + result.message);
            }
        } catch (error) {
            warmingUp.classList.add('hidden');
            form.classList.remove('hidden');
            alert('保存失败：' + error.message);
        }
    });
}

// ========== 登录页面 ==========
function initLoginPage() {
    const loginForm = document.getElementById('loginForm');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');

    loginForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        // 清空错误提示
        document.querySelectorAll('.error-msg').forEach(el => el.textContent = '');

        // 校验
        let valid = true;
        if (!username) {
            showError('username', '请输入用户名');
            valid = false;
        }
        if (!password) {
            showError('password', '请输入密码');
            valid = false;
        }

        if (!valid) return;

        try {
            const result = await api.login(username, password);

            if (result.success) {
                // 保存用户信息到 localStorage
                localStorage.setItem('userId', result.user_id);
                localStorage.setItem('username', result.username);
                if (result.ai_name) {
                    localStorage.setItem('aiName', result.ai_name);
                }

                // 登录成功，跳转聊天页面
                window.location.href = 'chat.html';
            } else {
                showError('username', result.message);
            }
        } catch (error) {
            showError('username', error.message || '登录失败，请重试');
        }
    });
}

// ========== 初始化页面 ==========
function initOnboardingPage() {
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const loading = document.getElementById('loading');
    const identitySelect = document.getElementById('identity_type');
    const identityDetailContainer = document.getElementById('identity_detail_container');

    // 身份详情模板
    const identityDetailTemplates = {
        student: `
            <div class="form-group">
                <label>学段</label>
                <select id="education_stage">
                    <option value="">请选择</option>
                    <option value="elementary">小学</option>
                    <option value="middle">初中</option>
                    <option value="high">高中</option>
                    <option value="college">大学</option>
                    <option value="graduate">研究生</option>
                </select>
            </div>
            <div class="form-group" id="major_group" style="display: none;">
                <label>专业方向（可选）</label>
                <input type="text" id="major" placeholder="如：计算机科学">
            </div>
        `,
        worker: `
            <div class="form-group">
                <label>所在行业（可选）</label>
                <input type="text" id="industry" placeholder="如：互联网">
            </div>
            <div class="form-group">
                <label>职位（可选）</label>
                <input type="text" id="job_title" placeholder="如：工程师">
            </div>
        `,
        teacher: `
            <div class="form-group">
                <label>任教学科（可选）</label>
                <input type="text" id="subject" placeholder="如：数学">
            </div>
            <div class="form-group">
                <label>教学学段（可选）</label>
                <input type="text" id="teaching_stage" placeholder="如：高中">
            </div>
        `,
        freelancer: `
            <div class="form-group">
                <label>从事领域（可选）</label>
                <input type="text" id="field" placeholder="如：独立开发">
            </div>
        `,
        other: `
            <div class="form-group">
                <label>身份描述（可选）</label>
                <input type="text" id="description" placeholder="简单描述你的身份">
            </div>
        `,
    };

    // 身份类型变化时动态展示详情字段
    identitySelect.addEventListener('change', function () {
        const type = this.value;
        identityDetailContainer.innerHTML = type ? (identityDetailTemplates[type] || '') : '';

        // 学生身份：监听学段变化，控制专业方向显示
        if (type === 'student') {
            const educationStageSelect = document.getElementById('education_stage');
            const majorGroup = document.getElementById('major_group');

            if (educationStageSelect && majorGroup) {
                educationStageSelect.addEventListener('change', function() {
                    const stage = this.value;
                    // 只有大学(college)和研究生(graduate)才显示专业方向
                    if (stage === 'college' || stage === 'graduate') {
                        majorGroup.style.display = 'block';
                    } else {
                        majorGroup.style.display = 'none';
                        // 清空专业方向输入
                        const majorInput = document.getElementById('major');
                        if (majorInput) majorInput.value = '';
                    }
                });
            }
        }
    });

    // 下一步按钮
    document.getElementById('nextBtn').addEventListener('click', function () {
        if (validateStep1()) {
            step1.classList.add('hidden');
            step2.classList.remove('hidden');
        }
    });

    // 上一步按钮
    document.getElementById('prevBtn').addEventListener('click', function () {
        step2.classList.add('hidden');
        step1.classList.remove('hidden');
    });

    // 提交按钮
    document.getElementById('submitBtn').addEventListener('click', async function () {
        if (validateStep2()) {
            const data = collectFormData();

            step2.classList.add('hidden');
            loading.classList.remove('hidden');

            try {
                const result = await api.onboarding(data);

                if (result.success) {
                    // 保存用户信息到 localStorage
                    localStorage.setItem('userId', result.user_id);
                    localStorage.setItem('username', data.username);
                    localStorage.setItem('aiName', data.ai_customization.ai_name);

                    // 跳转到聊天页面
                    window.location.href = 'chat.html';
                } else {
                    alert('初始化失败：' + result.message);
                    loading.classList.add('hidden');
                    step2.classList.remove('hidden');
                }
            } catch (error) {
                alert('初始化失败：' + error.message);
                console.error(error);
                loading.classList.add('hidden');
                step2.classList.remove('hidden');
            }
        }
    });
}

// 校验第一步
function validateStep1() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const identityType = document.getElementById('identity_type').value;
    let valid = true;

    // 清空错误提示
    document.querySelectorAll('#step1 .error-msg').forEach(el => el.textContent = '');

    if (!username) {
        showError('username', '请输入您的昵称');
        valid = false;
    } else if (username.length > 50) {
        showError('username', '昵称最多 50 个字符');
        valid = false;
    }

    if (!password) {
        showError('password', '请设置密码');
        valid = false;
    }

    if (!identityType) {
        showError('identity_type', '请选择您的身份类型');
        valid = false;
    }

    return valid;
}

// 校验第二步
function validateStep2() {
    const aiName = document.getElementById('ai_name').value.trim();
    const aiRole = document.getElementById('ai_role').value;
    let valid = true;

    document.querySelectorAll('#step2 .error-msg').forEach(el => el.textContent = '');

    if (!aiName) {
        showError('ai_name', '请给 AI 助手起个名字');
        valid = false;
    } else if (aiName.length > 20) {
        showError('ai_name', '名字最多 20 个字符');
        valid = false;
    }

    if (!aiRole) {
        showError('ai_role', '请选择 AI 助手的身份');
        valid = false;
    }

    return valid;
}

// 显示错误提示
function showError(fieldId, message) {
    const field = document.getElementById(fieldId);
    const errorEl = field.parentElement.querySelector('.error-msg');
    if (errorEl) {
        errorEl.textContent = message;
    }
}

// 收集表单数据
function collectFormData() {
    const identityType = document.getElementById('identity_type').value;
    const identityDetail = {};

    // 根据身份类型收集详情
    if (identityType === 'student') {
        const educationStage = document.getElementById('education_stage')?.value;
        const major = document.getElementById('major')?.value.trim();
        if (educationStage) identityDetail.education_stage = educationStage;
        if (major) identityDetail.major = major;
    } else if (identityType === 'worker') {
        const industry = document.getElementById('industry')?.value.trim();
        const jobTitle = document.getElementById('job_title')?.value.trim();
        if (industry) identityDetail.industry = industry;
        if (jobTitle) identityDetail.job_title = jobTitle;
    } else if (identityType === 'teacher') {
        const subject = document.getElementById('subject')?.value.trim();
        const teachingStage = document.getElementById('teaching_stage')?.value.trim();
        if (subject) identityDetail.subject = subject;
        if (teachingStage) identityDetail.teaching_stage = teachingStage;
    } else if (identityType === 'freelancer') {
        const field = document.getElementById('field')?.value.trim();
        if (field) identityDetail.field = field;
    } else if (identityType === 'other') {
        const description = document.getElementById('description')?.value.trim();
        if (description) identityDetail.description = description;
    }

    // 收集使用场景（第一步的复选框）
    const useCases = [];
    document.querySelectorAll('#step1 .checkbox-group input[type="checkbox"]:checked').forEach(cb => {
        useCases.push(cb.value);
    });

    // 收集性格特点（第二步的复选框）
    const personality = [];
    document.querySelectorAll('#step2 .checkbox-group input[type="checkbox"]:checked').forEach(cb => {
        personality.push(cb.value);
    });

    return {
        username: document.getElementById('username').value.trim(),
        password: document.getElementById('password').value,
        identity_type: identityType,
        identity_detail: Object.keys(identityDetail).length > 0 ? identityDetail : null,
        use_cases: useCases,
        interests: [],  // 暂时留空，表单中没有这个
        ai_customization: {
            ai_name: document.getElementById('ai_name').value.trim(),
            ai_role: document.getElementById('ai_role').value,
            personality: personality,
            communication_style: document.getElementById('communication_style').value,
        },
    };
}

// ========== 聊天页面 ==========
function initChatPage() {
    const userId = localStorage.getItem('userId');
    const aiName = localStorage.getItem('aiName') || 'AI 助手';
    const username = localStorage.getItem('username') || '用户';

    if (!userId) {
        window.location.href = 'index.html';
        return;
    }

    // 配置 marked + highlight.js
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            highlight: function(code, lang) {
                if (typeof hljs !== 'undefined') {
                    if (lang && hljs.getLanguage(lang)) {
                        return hljs.highlight(code, { language: lang }).value;
                    }
                    return hljs.highlightAuto(code).value;
                }
                return code;
            },
            breaks: true
        });
    }

    // 显示 AI 名字
    document.getElementById('ai_name_display').textContent = aiName;

    const chatMessages = document.getElementById('chat_messages');
    const userInput = document.getElementById('user_input');
    const sendBtn = document.getElementById('sendBtn');
    const logoutBtn = document.getElementById('logoutBtn');

    // 退出登录
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async function() {
            const sessionId = localStorage.getItem('sessionId');
            try {
                // 调用后端登出 API
                await api.logout(userId, sessionId);
            } catch (error) {
                console.error('登出 API 调用失败:', error);
            }
            // 清除本地存储
            localStorage.removeItem('userId');
            localStorage.removeItem('username');
            localStorage.removeItem('aiName');
            localStorage.removeItem('sessionId');
            window.location.href = 'index.html';
        });
    }

    // 发送消息
    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        // 显示用户消息
        appendMessage('user', message);
        userInput.value = '';

        // 创建 AI 消息容器（带思考动画）
        const aiMessageEl = appendMessage('ai', '', true);
        let fullResponse = '';

        try {
            await api.chat(
                userId,
                message,
                // onChunk - 流式接收内容
                (chunk) => {
                    fullResponse += chunk;
                    // 流式渲染 Markdown
                    renderAIMarkdown(aiMessageEl, fullResponse);
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                },
                // onDone - 完成
                (data) => {
                    console.log('对话完成:', data);
                    // 移除思考动画
                    removeThinkingAnimation(aiMessageEl);
                }
            );
        } catch (error) {
            console.error(error);
            removeThinkingAnimation(aiMessageEl);
            aiMessageEl.querySelector('.message-content').textContent = '网络错误，请重试';
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
}

// 渲染 AI 消息的 Markdown
function renderAIMarkdown(messageEl, content) {
    if (typeof marked !== 'undefined') {
        const html = marked.parse(content);
        messageEl.querySelector('.message-content').innerHTML = html;
        // 高亮代码块
        if (typeof hljs !== 'undefined') {
            messageEl.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        }
    }
}

// 移除思考动画
function removeThinkingAnimation(messageEl) {
    const thinkingEl = messageEl.querySelector('.thinking-indicator');
    if (thinkingEl) {
        thinkingEl.remove();
    }
}

// 添加消息到聊天窗口
function appendMessage(role, content, showThinking = false) {
    const chatMessages = document.getElementById('chat_messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    // 获取头像显示文字
    const aiName = localStorage.getItem('aiName') || 'AI';
    const username = localStorage.getItem('username') || 'U';
    const avatarText = role === 'ai' ? aiName.charAt(0).toUpperCase() : username.charAt(0).toUpperCase();

    // 格式化时间
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

    if (role === 'ai') {
        // AI 消息
        let thinkingHtml = '';
        if (showThinking || content === '') {
            // 思考动画放在 message-body 外面，定位到气泡右上角
            thinkingHtml = `
                <div class="thinking-indicator">
                    <span class="thinking-dot"></span>
                    <span class="thinking-dot"></span>
                    <span class="thinking-dot"></span>
                </div>
            `;
        }

        let contentHtml = '';
        if (content) {
            const renderedContent = typeof marked !== 'undefined' ? marked.parse(content) : escapeHtml(content);
            contentHtml = `<div class="message-content">${renderedContent}</div>`;
        } else {
            contentHtml = '<div class="message-content"></div>';
        }

        messageDiv.innerHTML = `
            <div class="avatar">${avatarText}</div>
            <div class="message-body-wrapper">
                ${thinkingHtml}
                <div class="message-body">
                    ${contentHtml}
                    <span class="message-time">${time}</span>
                </div>
            </div>
        `;
    } else {
        // 用户消息保持纯文本
        messageDiv.innerHTML = `
            <div class="avatar">${avatarText}</div>
            <div class="message-body">
                <div class="message-content">${escapeHtml(content)}</div>
                <span class="message-time">${time}</span>
            </div>
        `;
    }

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageDiv;
}

// HTML 转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
