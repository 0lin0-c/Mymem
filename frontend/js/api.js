// API 配置
const API_BASE_URL = 'http://localhost:8002';

// API 请求封装
const api = {
    // 用户登录
    async login(username, password) {
        const response = await fetch(`${API_BASE_URL}/v1/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password }),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '登录失败');
        }
        return response.json();
    },

    // 用户登出
    async logout(userId, sessionId) {
        const params = new URLSearchParams({ user_id: userId });
        if (sessionId) {
            params.append('session_id', sessionId);
        }
        const response = await fetch(`${API_BASE_URL}/v1/auth/logout?${params}`, {
            method: 'POST',
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '登出失败');
        }
        return response.json();
    },

    // 更新 LLM 设置
    async updateLLMSettings(data) {
        const response = await fetch(`${API_BASE_URL}/v1/user/llm-settings`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '保存失败');
        }
        return response.json();
    },

    // 获取 LLM 设置状态
    async getLLMSettings(userId) {
        const response = await fetch(`${API_BASE_URL}/v1/user/llm-settings/${userId}`);
        if (!response.ok) {
            throw new Error('获取状态失败');
        }
        return response.json();
    },

    // 用户初始化
    async onboarding(data) {
        const response = await fetch(`${API_BASE_URL}/v1/user/onboarding`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '初始化失败');
        }
        return response.json();
    },

    // 发送聊天消息（流式）
    async chat(userId, message, onChunk, onDone) {
        const sessionId = localStorage.getItem('sessionId') || generateSessionId();
        localStorage.setItem('sessionId', sessionId);

        const response = await fetch(`${API_BASE_URL}/v1/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                query: message,
                user_id: userId,
                modality: 'text',
            }),
        });

        if (!response.ok) {
            throw new Error('请求失败');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value);
            const lines = text.split('\n').filter(line => line.trim());

            for (const line of lines) {
                try {
                    const data = JSON.parse(line);
                    if (data.type === 'content') {
                        onChunk(data.text);
                    } else if (data.type === 'done') {
                        onDone(data);
                    } else if (data.type === 'error') {
                        throw new Error(data.message);
                    }
                } catch (e) {
                    // 忽略解析错误
                }
            }
        }
    },
};

// 生成会话 ID
function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}
