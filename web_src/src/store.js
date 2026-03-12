/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import {ref, reactive, computed, nextTick} from 'vue'

// --- State ---
export const isDark = ref(localStorage.getItem('lexisync-theme') === 'dark')
const checkInitialAuth = () => {
    if (new URLSearchParams(window.location.search).get('token')) return false;
    return !!(localStorage.getItem('cloud_session') || sessionStorage.getItem('cloud_session'));
}

export const showAuthDialog = ref(!checkInitialAuth());
export const loading = ref(checkInitialAuth());
export const authTab = ref('account')
export const authError = ref('')
export const loginForm = reactive({username: '', password: ''})
export const tokenForm = reactive({token: '', displayName: ''})
export const rememberMe = ref(true)
export const sessionToken = ref('')
export const currentUser = reactive({name: '', role: 'viewer'})
export const i18n = ref({})
export const tableData = ref([])
export const total = ref(0)
export const currentPage = ref(1)
export const pageSize = ref(50)
export const searchQuery = ref('')
export const statusFilter = ref('all')
export const project = reactive({name: '', source_lang: '', target_lang: ''})
export const stats = reactive({reviewed: 0, translated: 0, fuzzy: 0, untranslated: 0, total: 0})
export const onlineUsers = ref({})
export const activeRowId = ref(null)
export const showFab = ref(false)
export const isChatOpen = ref(false)
export const chatMessages = ref([])
export const chatInput = ref('')
export const wsState = ref('disconnected')
export const toasts = ref([])
export const globalActiveEditors = reactive({})

let ws = null
let wsReconnectTimer = null
let wsAttempts = 0
const MAX_WS_RETRY = 8
const INITIAL_RECONNECT_DELAY = 2000
let toastSeq = 0
let searchTimer = null
let fetchController = null

// --- Computed ---
export const t = (key) => i18n.value[key] || key
export const progressPct = computed(() => stats.total ? Math.round((stats.reviewed + stats.translated) / stats.total * 100) : 0)
export const onlineUsersArray = computed(() => Object.entries(onlineUsers.value).map(([name, d]) => ({name, ...d})))
export const wsStateLabel = computed(() => ({
    connecting: 'Connecting...',
    connected: 'Connected',
    reconnecting: 'Reconnecting...',
    disconnected: 'Disconnected',
    failed: 'Connection failed'
}[wsState.value] || ''))
export const filterTabs = computed(() => [
    {key: 'all', label: 'All', count: stats.total},
    {key: 'untranslated', label: 'Untranslated', count: stats.untranslated},
    {key: 'fuzzy', label: 'Fuzzy', count: stats.fuzzy},
    {key: 'translated', label: 'Translated', count: stats.translated},
    {key: 'reviewed', label: 'Reviewed', count: stats.reviewed},
])

// --- Methods ---
export const toastShow = (message, type = 'info', duration = 3000) => {
    const id = ++toastSeq
    toasts.value.push({id, message, type, leaving: false})
    if (duration > 0) setTimeout(() => toastDismiss(id), duration)
    return id
}

export const toastDismiss = (id) => {
    const t_obj = toasts.value.find(x => x.id === id)
    if (t_obj) {
        t_obj.leaving = true;
        setTimeout(() => {
            toasts.value = toasts.value.filter(x => x.id !== id)
        }, 280)
    }
}

export const applyTheme = (dark) => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('lexisync-theme', dark ? 'dark' : 'light');
}

export const toggleTheme = () => {
    isDark.value = !isDark.value;
    applyTheme(isDark.value);
}

export const avatarColor = (name) => {
    const PALETTE = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];
    let h = 0;
    for (const c of (name || '?')) h = ((h * 31) + c.charCodeAt(0)) >>> 0;
    return PALETTE[h % PALETTE.length];
}

export const formatTime = (iso) => {
    const d = new Date(iso);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}

export const connectWebSocket = () => {
    clearTimeout(wsReconnectTimer)

    if (ws) {
        try {
            ws.close()
        } catch (_) {
        }
    }
    wsState.value = 'connecting'
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${proto}//${location.host}/ws?token=${sessionToken.value}`)

    ws.onopen = () => {
        wsState.value = 'connected';
        wsAttempts = 0;
        toastShow(t('Connected'), 'success', 2200);
        fetchOnlineUsers()
    }
    ws.onmessage = (ev) => {
        try {
            handleWsMsg(JSON.parse(ev.data))
        } catch (_) {
        }
    }
    ws.onclose = (ev) => {
        if (wsState.value === 'disconnected') return

        if (ev.code === 1008) {
            wsState.value = 'disconnected'
            checkSessionAndInit()
            return
        }

        wsAttempts++
        if (wsAttempts > MAX_WS_RETRY) {
            wsState.value = 'failed';
            toastShow(t('Connection failed'), 'error', 0);
            return
        }

        const delay = Math.min(INITIAL_RECONNECT_DELAY * Math.pow(2, wsAttempts - 1), 30000);

        wsState.value = 'reconnecting'
        toastShow(`${t('Reconnecting...')} (${wsAttempts}/${MAX_WS_RETRY})`, 'warning', delay - 200)
        wsReconnectTimer = setTimeout(connectWebSocket, delay)
    }
}

export const wsSend = (obj) => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj))
}

export const handleWsMsg = (msg) => {
    switch (msg.type) {
        case 'DATA_UPDATE': {
            const item = tableData.value.find(r => r.id === msg.data.ts_id)
            if (item) {
                const isEditingThisRow = activeRowId.value === item.id

                if (msg.data.new_text !== null && msg.data.new_text !== undefined) {
                    if (isEditingThisRow && msg.data.user !== currentUser.name) {
                        toastShow(`⚠️ ${msg.data.user || t('Someone')} ${t('just updated this entry. Your changes will overwrite theirs on save.')}`, 'warning', 5000)
                    } else {
                        if (item.is_plural) item.plural_translations[msg.data.plural_index] = msg.data.new_text;
                        else item.translation = msg.data.new_text;
                    }
                }
                if (msg.data.is_reviewed !== null && msg.data.is_reviewed !== undefined) item.is_reviewed = msg.data.is_reviewed
                if (msg.data.is_fuzzy !== null && msg.data.is_fuzzy !== undefined) item.is_fuzzy = msg.data.is_fuzzy
            }
            break
        }
        case 'FOCUS_UPDATE': {
            // 更新全局状态
            if (!globalActiveEditors[msg.data.ts_id]) globalActiveEditors[msg.data.ts_id] = []

            if (msg.data.status === 'editing') {
                if (!globalActiveEditors[msg.data.ts_id].includes(msg.data.user)) {
                    globalActiveEditors[msg.data.ts_id].push(msg.data.user)
                }
            } else {
                globalActiveEditors[msg.data.ts_id] = globalActiveEditors[msg.data.ts_id].filter(u => u !== msg.data.user)
            }

            // 同步更新到视图
            const item = tableData.value.find(r => r.id === msg.data.ts_id)
            if (item) {
                item.active_editors = globalActiveEditors[msg.data.ts_id]
            }

            if (onlineUsers.value[msg.data.user] !== undefined) {
                onlineUsers.value[msg.data.user].editingId = msg.data.status === 'editing' ? msg.data.ts_id : null
            }
            break
        }
        case 'USER_CONNECTED':
        case 'USER_DISCONNECTED': {
            rebuildOnlineUsers(msg.data.online_users)
            break
        }
        case 'CHAT_MESSAGE': {
            chatMessages.value.push(msg.data)
            if (!isChatOpen.value) toastShow(`${msg.data.user}: ${msg.data.text}`, 'info', 3000)
            nextTick(() => {
                const el = document.getElementById('chatMessages')
                if (el) el.scrollTop = el.scrollHeight
            })
            break
        }
    }
}

export const rebuildOnlineUsers = (list) => {
    if (!Array.isArray(list)) return
    const next = {}
    const onlineNames = list.map(u => u.name)

    for (const u of list) {
        next[u.name] = {role: u.role, editingId: onlineUsers.value[u.name]?.editingId || null}
    }
    onlineUsers.value = next

    // 清理掉线用户的锁定状态
    for (const id in globalActiveEditors) {
        globalActiveEditors[id] = globalActiveEditors[id].filter(name => onlineNames.includes(name))
        const item = tableData.value.find(r => String(r.id) === String(id))
        if (item) item.active_editors = globalActiveEditors[id]
    }
}

export const fetchOnlineUsers = async () => {
    try {
        const res = await fetch(`/api/v1/users?token=${sessionToken.value}`, { cache: 'no-store' });
        if (res.ok) rebuildOnlineUsers((await res.json()).users || []);
    } catch (_) {
    }
}

export const saveSession = (token) => {
    sessionToken.value = token
    sessionStorage.setItem('cloud_session', token)
}

export const loadSession = () => {
    const urlTok = new URLSearchParams(location.search).get('token')
    if (urlTok) {
        tokenForm.token = urlTok
        authTab.value = 'token'
        history.replaceState({}, document.title, location.pathname)
        return null
    }
    return localStorage.getItem('cloud_session') || sessionStorage.getItem('cloud_session')
}

export const loginAccount = async () => {
    if (!loginForm.username || !loginForm.password) {
        authError.value = 'Fill all fields';
        return
    }
    loading.value = true;
    authError.value = ''
    try {
        const res = await fetch('/api/v1/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(loginForm)
        })
        if (!res.ok) throw new Error('Invalid credentials')
        const data = await res.json()

        saveSession(data.token)
        if (rememberMe.value) {
            localStorage.setItem('lexisync_auth', JSON.stringify({
                type: 'account',
                username: loginForm.username,
                password: btoa(loginForm.password)
            }))
        } else {
            localStorage.removeItem('lexisync_auth')
        }

        currentUser.name = data.name;
        currentUser.role = data.role
        await initApp()
    } catch (e) {
        authError.value = e.message
    } finally {
        loading.value = false
    }
}

export const loginToken = async () => {
    if (!tokenForm.token) {
        authError.value = 'Token required';
        return
    }
    loading.value = true;
    authError.value = ''
    try {
        const res = await fetch('/api/v1/login-token', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({token: tokenForm.token, display_name: tokenForm.displayName})
        })
        if (!res.ok) throw new Error('Invalid or expired token')
        const data = await res.json()

        saveSession(data.token)
        if (rememberMe.value) {
            localStorage.setItem('lexisync_auth', JSON.stringify({
                type: 'token',
                token: tokenForm.token,
                displayName: tokenForm.displayName
            }))
        } else {
            localStorage.removeItem('lexisync_auth')
        }

        currentUser.name = data.name;
        currentUser.role = data.role
        await initApp()
    } catch (e) {
        authError.value = e.message
    } finally {
        loading.value = false
    }
}

export const loginRemembered = async (rememberToken) => {
    try {
        const res = await fetch('/api/v1/login-remembered', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({remember_token: rememberToken})
        });
        if (!res.ok) throw new Error('Remember token invalid');
        const data = await res.json();

        sessionToken.value = data.token;
        sessionStorage.setItem('cloud_session', data.token);

        currentUser.name = data.name;
        currentUser.role = data.role;
        await initApp();
        return true;
    } catch (e) {
        localStorage.removeItem('lexisync_remember');
        return false;
    }
};

export const checkSessionAndInit = async () => {
    // 1. 尝试使用当前内存或 Session 中的 Token
    const existingToken = sessionStorage.getItem('cloud_session')

    if (existingToken) {
        sessionToken.value = existingToken
        try {
            const res = await fetch(`/api/v1/me?token=${sessionToken.value}`, { cache: 'no-store' })
            if (res.ok) {
                const data = await res.json()
                currentUser.name = data.name;
                currentUser.role = data.role
                await initApp()
                return // 成功则直接返回
            }
        } catch (e) {
        }
    }

    const savedAuthStr = localStorage.getItem('lexisync_auth')
    if (savedAuthStr) {
        try {
            const authData = JSON.parse(savedAuthStr)
            if (authData.type === 'account') {
                loginForm.username = authData.username
                loginForm.password = atob(authData.password)
                rememberMe.value = true
                await loginAccount()
                return
            } else if (authData.type === 'token') {
                tokenForm.token = authData.token
                tokenForm.displayName = authData.displayName
                rememberMe.value = true
                await loginToken()
                return
            }
        } catch (e) {
            localStorage.removeItem('lexisync_auth')
        }
    }

    // 3. 如果都没有，显示登录框
    showAuthDialog.value = true
}


export const initApp = async () => {
    loading.value = true
    try {
        const resI18n = await fetch(`/api/v1/i18n?token=${sessionToken.value}`, { cache: 'no-store' })
        if (resI18n.ok) i18n.value = await resI18n.json()
        await fetchData()
        showAuthDialog.value = false
        connectWebSocket()
    } catch (e) {
        authError.value = "Failed to initialize app."
    } finally {
        loading.value = false
    }
}

export const logout = () => {
    sessionStorage.removeItem('cloud_session')
    localStorage.removeItem('lexisync_auth')
    sessionToken.value = '';
    wsState.value = 'disconnected'
    if (ws) {
        try {
            ws.close()
        } catch (_) {
        }
        ws = null
    }
    onlineUsers.value = {};
    showAuthDialog.value = true
}

export const fetchData = async () => {
    if (fetchController) fetchController.abort()
    fetchController = new AbortController()
    const {signal} = fetchController

    loading.value = true
    try {
        const qs = `token=${sessionToken.value}`
        const [pRes, sRes] = await Promise.all([
            fetch(`/api/v1/project?${qs}`, { signal, cache: 'no-store' }),
            fetch(`/api/v1/strings?${qs}&page=${currentPage.value}&page_size=${pageSize.value}&search=${encodeURIComponent(searchQuery.value)}&status=${statusFilter.value === 'all' ? '' : statusFilter.value}`, { signal, cache: 'no-store' })
        ])
        if (!pRes.ok || !sRes.ok) throw new Error('Fetch')

        const pData = await pRes.json()
        Object.assign(project, pData)
        Object.assign(stats, {
            total: pData.total,
            reviewed: pData.reviewed,
            translated: pData.translated,
            fuzzy: pData.fuzzy,
            untranslated: pData.untranslated
        })

        const sData = await sRes.json()

        // 从全局状态中映射最新的编辑情况
        tableData.value = (sData.items || []).map(item => {
            item.active_editors = globalActiveEditors[item.id] || []
            return item
        });
        total.value = sData.total ?? 0
    } catch (e) {
        if (e.name !== 'AbortError') {
            toastShow(t('Sync failed'), 'error')
        }
    } finally {
        if (!signal.aborted) {
            loading.value = false
        }
    }
}

export const updateTranslation = async (item, pIdx = 0) => {
    if (currentUser.role === 'viewer') return
    wsSend({action: 'blur', ts_id: item.id})
    activeRowId.value = null;
    const text = item.is_plural ? item.plural_translations[pIdx] : item.translation
    try {
        const res = await fetch(`/api/v1/update?token=${sessionToken.value}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ts_id: item.id, new_text: text, plural_index: pIdx})
        })
        if (!res.ok) throw new Error()
        toastShow(t('Saved'), 'success', 1400)
    } catch (_) {
        toastShow(t('Save failed'), 'error')
    }
}

export const toggleStatus = async (item, type) => {
    if (currentUser.role === 'viewer') return
    if (type === 'reviewed' && currentUser.role === 'translator') {
        toastShow(t('Permission Denied'), 'error');
        return
    }

    const payload = {ts_id: item.id}
    if (type === 'reviewed') {
        payload.is_reviewed = !item.is_reviewed;
        if (payload.is_reviewed) payload.is_fuzzy = false
    } else {
        payload.is_fuzzy = !item.is_fuzzy;
        if (payload.is_fuzzy) payload.is_reviewed = false
    }

    item.is_reviewed = payload.is_reviewed ?? item.is_reviewed
    item.is_fuzzy = payload.is_fuzzy ?? item.is_fuzzy

    try {
        await fetch(`/api/v1/update?token=${sessionToken.value}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        })
    } catch (e) {
        toastShow(t('Sync failed'), 'error');
        fetchData()
    }
}

export const requestAITranslation = async (item) => {
    if (currentUser.role === 'viewer') return
    toastShow(t('AI Translate') + '...', 'info', 2000)
    try {
        const res = await fetch(`/api/v1/ai-translate?token=${sessionToken.value}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ts_id: item.id})
        })
        if (!res.ok) throw new Error()
    } catch (_) {
        toastShow(t('Sync failed'), 'error')
    }
}

export const sendChatMessage = () => {
    if (chatInput.value.trim()) {
        wsSend({action: 'chat', message: chatInput.value});
        chatInput.value = ''
    }
}
export const onEditorFocus = (row) => {
    if (currentUser.role !== 'viewer') {
        activeRowId.value = row.id;
        wsSend({action: 'focus', ts_id: row.id})
    }
}
export const setFilter = (key) => {
    statusFilter.value = key;
    currentPage.value = 1;
    fetchData()
}
export const onPageChange = () => {
    fetchData();
    document.getElementById('mainScroll')?.scrollTo(0, 0)
}
export const onPageSizeChange = (newSize) => {
    pageSize.value = newSize;
    if (currentPage.value === 1) {
        fetchData();
    } else {
        currentPage.value = 1;
    }
}
export const handleSearch = () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        currentPage.value = 1;
        fetchData()
    }, 450)
}

export const getStatusKey = (r) => {
    if (r.is_reviewed) return 'reviewed';
    if (r.is_fuzzy) return 'fuzzy';
    if (r.translation) return 'translated';
    return 'untranslated'
}
export const tableRowClassName = ({row}) => {
    const st = getStatusKey(row);
    return `row-${st}`
}
export const hlPh = (text) => {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/(\{[^{}]+\}|%[0-9$]*[hlLzZjpt]*[a-zA-Z])/g, '<span class="hl-ph">$1</span>')
}
export const scrollToTop = () => {
    window.scrollTo({top: 0, behavior: 'smooth'});
}

export const cleanupStore = () => {
    clearTimeout(searchTimer)
    clearTimeout(wsReconnectTimer)
    if (fetchController) fetchController.abort()
    if (ws) {
        try {
            ws.close()
        } catch (_) {
        }
    }
}