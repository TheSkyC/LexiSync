/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import {ref, computed, nextTick, watch} from 'vue'
import {ElMessageBox} from 'element-plus'
import {sessionToken, currentUser, t, checkSessionAndInit, authFetch, hasPermission, logout} from './auth.js'
import {
    project,
    tableData,
    globalActiveEditors,
    stats,
    getStatusKey,
    fetchProjectStats,
    fetchData,
    activeRowId,
    currentPage
} from './project.js'
import {toastShow, toastDismiss} from './ui.js'
import {registerWsSend} from './wsClient.js'

export const wsState = ref('disconnected')
export const wsStateLabel = computed(() => ({
    connecting: 'Connecting...',
    connected: 'Connected',
    reconnecting: 'Reconnecting...',
    'reconnecting-fixed': 'Reconnecting...',
    disconnected: 'Disconnected',
    failed: 'Connection failed'
}[wsState.value] || ''))

export const wsReconnectCountdown = ref(0)

export const onlineUsers = ref({})
export const onlineUsersArray = computed(() =>
    Object.entries(onlineUsers.value).map(([name, d]) => ({name, ...d}))
)

export const isChatOpen = ref(false)
export const isUsersOpen = ref(false)
export const chatMessages = ref([])
export const chatInput = ref('')
export const unreadChatCount = ref(0)

let ws = null
let wsReconnectTimer = null
let wsCountdownTimer = null
let wsAttempts = 0
let hasConnectedOnce = false
let pingInterval = null
let failedToastId = null

// ── 重连参数 ────────────────────────────────────────────────────
const MAX_WS_RETRY = 8                  // 指数退避最大重试次数
const INITIAL_RECONNECT_DELAY = 2000    // 初始退避基数（ms）
const FIXED_RECONNECT_INTERVAL = 30000  // 超过 MAX_WS_RETRY 后的固定重连间隔（ms）
const JITTER_RANGE = 5000               // 抖动范围 ±5s（ms）

// ── 页面可见性 ──────────────────────────────────────────────────
// 当标签页隐藏时暂停重连，切回时立即恢复
let pendingReconnectOnVisible = false

const onVisibilityChange = () => {
    if (document.visibilityState === 'visible') {
        if (pendingReconnectOnVisible) {
            pendingReconnectOnVisible = false
            wsReconnectCountdown.value = 0
            _clearCountdown()
            connectWebSocket()
        }
    } else {
        if (wsReconnectTimer !== null && (wsState.value === 'reconnecting' || wsState.value === 'reconnecting-fixed')) {
            clearTimeout(wsReconnectTimer)
            wsReconnectTimer = null
            _clearCountdown()
            pendingReconnectOnVisible = true
        }
    }
}

document.addEventListener('visibilitychange', onVisibilityChange)

const withJitter = (base, jitter = JITTER_RANGE) => {
    const offset = (Math.random() * 2 - 1) * jitter   // [-jitter, +jitter]
    return Math.max(500, Math.round(base + offset))
}

const _clearCountdown = () => {
    clearInterval(wsCountdownTimer)
    wsCountdownTimer = null
    wsReconnectCountdown.value = 0
}

const _startCountdown = (delayMs) => {
    _clearCountdown()
    wsReconnectCountdown.value = Math.ceil(delayMs / 1000)
    wsCountdownTimer = setInterval(() => {
        wsReconnectCountdown.value = Math.max(0, wsReconnectCountdown.value - 1)
        if (wsReconnectCountdown.value <= 0) _clearCountdown()
    }, 1000)
}

// ── 调度下一次重连 ──────────────────────────────────────────────
const _scheduleReconnect = (delayMs, stateLabel = 'reconnecting') => {
    clearTimeout(wsReconnectTimer)
    wsReconnectTimer = null

    // 页面隐藏时不启动定时器，只做标记
    if (document.visibilityState === 'hidden') {
        wsState.value = stateLabel
        pendingReconnectOnVisible = true
        return
    }

    wsState.value = stateLabel
    _startCountdown(delayMs)
    wsReconnectTimer = setTimeout(() => {
        wsReconnectTimer = null
        connectWebSocket()
    }, delayMs)
}

watch(isChatOpen, (isOpen) => {
    if (isOpen) unreadChatCount.value = 0
})

const getChatStorageKey = () => {
    const pName = project.name || 'default'
    const uName = currentUser.name || 'anonymous'
    return `lexisync_chat_${pName}_${uName}`
}

const loadChatHistory = () => {
    try {
        const saved = localStorage.getItem(getChatStorageKey())
        if (saved) chatMessages.value = JSON.parse(saved)
    } catch (_) {
        chatMessages.value = []
    }
}

const saveChatHistory = () => {
    try {
        if (chatMessages.value.length > 200) {
            chatMessages.value = chatMessages.value.slice(-200)
        }
        localStorage.setItem(getChatStorageKey(), JSON.stringify(chatMessages.value))
    } catch (_) {
    }
}

export const clearChatHistory = () => {
    chatMessages.value = []
    try {
        localStorage.removeItem(getChatStorageKey())
    } catch (_) {
    }
}

// 踢人功能
export const kickUser = async (username) => {
    if (currentUser.role !== 'admin') return
    try {
        const res = await authFetch('/api/v1/kick', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username})
        })
        if (!res.ok) throw new Error(t('Failed to kick user'))
        toastShow(t('User kicked successfully'), 'success')
    } catch (e) {
        toastShow(e.message, 'error')
    }
}

// 封禁 IP 功能
export const banUserIp = async (ip, username) => {
    if (currentUser.role !== 'admin') return
    try {
        await new Promise((resolve, reject) => {
            ElMessageBox.confirm(
                `${t('Are you sure you want to ban the IP for')} ${username}?`,
                t('Warning'),
                {
                    confirmButtonText: t('Yes'),
                    cancelButtonText: t('Cancel'),
                    type: 'warning',
                    beforeClose: (action, instance, done) => {
                        if (action === 'confirm') {
                            instance.confirmButtonLoading = true
                            resolve()
                            done()
                        } else {
                            reject('cancel')
                            done()
                        }
                    }
                }
            )

            setTimeout(() => {
                const btn = document.querySelector('.el-message-box__btns .el-button--primary')
                if (btn) {
                    const originalText = btn.innerText
                    let countdown = 3

                    btn.disabled = true
                    btn.classList.add('is-disabled')
                    btn.innerHTML = `<span>${originalText} (${countdown}s)</span>`

                    const timer = setInterval(() => {
                        countdown--
                        if (countdown <= 0) {
                            clearInterval(timer)
                            btn.disabled = false
                            btn.classList.remove('is-disabled')
                            btn.innerHTML = `<span>${originalText}</span>`
                        } else {
                            btn.innerHTML = `<span>${originalText} (${countdown}s)</span>`
                        }
                    }, 1000)
                }
            }, 10)
        })

        const res = await authFetch('/api/v1/ban', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ip, username})
        })
        if (!res.ok) throw new Error(t('Failed to ban IP'))
        toastShow(t('IP banned successfully'), 'success')
    } catch (e) {
        if (e !== 'cancel') toastShow(e.message, 'error')
    }
}

const _wsSend = (obj) => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj))
}
registerWsSend(_wsSend)
export const wsSend = _wsSend

export const rebuildOnlineUsers = (list) => {
    if (!Array.isArray(list)) return
    const onlineNames = list.map(u => u.name)
    const next = {}
    for (const u of list) next[u.name] = {
        role: u.role,
        ip: u.ip,
        editingId: onlineUsers.value[u.name]?.editingId ?? null
    }
    onlineUsers.value = next
    for (const id in globalActiveEditors) {
        globalActiveEditors[id] = globalActiveEditors[id].filter(n => onlineNames.includes(n))
        const item = tableData.value.find(r => String(r.id) === String(id))
        if (item) item.active_editors = globalActiveEditors[id]
    }
}

export const fetchOnlineUsers = async () => {
    try {
        const res = await authFetch('/api/v1/users', {cache: 'no-store'})
        if (res.ok) rebuildOnlineUsers((await res.json()).users || [])
    } catch (_) {
    }
}

const handleWsMsg = (msg) => {
    switch (msg.type) {
        case 'BULK_DATA_UPDATE': {
            const {user, changes} = msg.data;
            let needs_stats_refresh = false;

            const isFromMe = String(user).trim() === String(currentUser.name).trim();
            changes.forEach(change => {
                const item = tableData.value.find(r => r.id === change.ts_id);
                if (item) {
                    const oldStatus = getStatusKey(item);
                    item.isAiLoading = false;

                    if (change.new_text != null) {
                        if (activeRowId.value === item.id && !isFromMe) {
                            item.conflictData = {
                                serverText: change.new_text,
                                user: user || 'Someone',
                                plural_index: change.plural_index ?? 0,
                            };
                        } else {
                            if (item.is_plural) {
                                item.plural_translations[change.plural_index ?? 0] = change.new_text;
                            } else {
                                item.translation = change.new_text;
                            }
                            item.conflictData = null;
                        }
                    }
                    if (change.is_reviewed != null) item.is_reviewed = change.is_reviewed;
                    if (change.is_fuzzy != null) item.is_fuzzy = change.is_fuzzy;
                    const newStatus = getStatusKey(item);
                    if (oldStatus !== newStatus) {
                        stats[oldStatus] = Math.max(0, (stats[oldStatus] ?? 0) - 1);
                        stats[newStatus] = (stats[newStatus] ?? 0) + 1;
                    }
                } else {
                    needs_stats_refresh = true;
                }
            });
            if (needs_stats_refresh) {
                fetchProjectStats();
            }
            break;
        }
        case 'AI_STATUS_UPDATE': {
            const item = tableData.value.find(r => r.id === msg.data.ts_id)
            if (item) {
                item.isAiLoading = msg.data.status === 'loading'
            }
            break
        }
        case 'FOCUS_UPDATE': {
            const editors = globalActiveEditors[msg.data.ts_id] ?? (globalActiveEditors[msg.data.ts_id] = [])
            if (msg.data.status === 'editing') {
                if (!editors.includes(msg.data.user)) editors.push(msg.data.user)
            } else {
                globalActiveEditors[msg.data.ts_id] = editors.filter(u => u !== msg.data.user)
            }
            const item = tableData.value.find(r => r.id === msg.data.ts_id)
            if (item) item.active_editors = globalActiveEditors[msg.data.ts_id]
            if (onlineUsers.value[msg.data.user] !== undefined)
                onlineUsers.value[msg.data.user].editingId =
                    msg.data.status === 'editing' ? msg.data.ts_id : null
            break
        }
        case 'FORCE_BLUR': {
            const ts_id = msg.data.ts_id;
            if (globalActiveEditors[ts_id]) {
                delete globalActiveEditors[ts_id];
            }
            const item = tableData.value.find(r => r.id === ts_id);
            if (item) {
                item.active_editors = [];
            }
            if (activeRowId.value === ts_id) {
                activeRowId.value = null;
                const el = document.querySelector(`[data-row-id="${ts_id}"] textarea`);
                el?.blur();
            }
            for (const user in onlineUsers.value) {
                if (onlineUsers.value[user].editingId === ts_id) {
                    onlineUsers.value[user].editingId = null;
                }
            }
            break;
        }
        case 'USER_CONNECTED':
        case 'USER_DISCONNECTED':
            rebuildOnlineUsers(msg.data.online_users)
            break
        case 'CHAT_MESSAGE':
            chatMessages.value.push(msg.data)
            saveChatHistory()
            if (!isChatOpen.value && String(msg.data.user).trim() !== String(currentUser.name).trim()) {
                unreadChatCount.value++
                toastShow(`${msg.data.user}: ${msg.data.text}`, 'info', 3000)
            }
            nextTick(() => {
                const el = document.getElementById('chatMessages')
                if (el) el.scrollTop = el.scrollHeight
            })
            break
        case 'HOST_STATE_CHANGED':
            toastShow(t('Host state changed. Refreshing...'), 'warning', 3000)
            activeRowId.value = null
            currentPage.value = 1
            tableData.value = []
            fetchData()
            break
    }
}

export const connectWebSocket = () => {
    clearTimeout(wsReconnectTimer)
    wsReconnectTimer = null
    _clearCountdown()
    pendingReconnectOnVisible = false

    if (ws) {
        ws.onclose = null
        ws.onerror = null
        try {
            ws.close()
        } catch (_) {
        }
        ws = null
    }

    wsState.value = 'connecting'

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${proto}//${location.host}/ws?token=${sessionToken.value}`)

    ws.onopen = () => {
        wsState.value = 'connected'
        wsAttempts = 0
        _clearCountdown()

        // 撤掉持久的"连接失败"toast
        if (failedToastId !== null) {
            toastDismiss(failedToastId)
            failedToastId = null
        }

        toastShow(t('Connected'), 'success', 2200)
        fetchOnlineUsers()
        loadChatHistory()

        if (hasConnectedOnce) {
            fetchData()
        }
        hasConnectedOnce = true

        clearInterval(pingInterval)
        pingInterval = setInterval(() => {
            _wsSend({action: 'ping'})
        }, 20000)
    }

    ws.onmessage = (ev) => {
        try {
            handleWsMsg(JSON.parse(ev.data))
        } catch (_) {
        }
    }

    ws.onclose = (ev) => {
        clearInterval(pingInterval)

        // 已被主动断开，不重连
        if (wsState.value === 'disconnected') return

        // 被服务端以 1008 踢出，不重连
        if (ev.code === 1008) {
            wsState.value = 'disconnected'
            logout()
            toastShow(t('You have been disconnected by the host.'), 'error', 5000)
            return
        }

        wsAttempts++

        if (wsAttempts <= MAX_WS_RETRY) {
            // ── 阶段一：指数退避重连 ──────────────────────────
            const baseDelay = Math.min(INITIAL_RECONNECT_DELAY * 2 ** (wsAttempts - 1), 30000)
            const delay = withJitter(baseDelay, Math.min(baseDelay * 0.3, 3000))
            toastShow(
                `${t('Reconnecting...')} (${wsAttempts}/${MAX_WS_RETRY})`,
                'warning',
                delay - 200
            )
            _scheduleReconnect(delay, 'reconnecting')
        } else {
            // ── 阶段二：固定间隔重连 ───────────────
            if (wsState.value !== 'reconnecting-fixed') {
                if (failedToastId !== null) toastDismiss(failedToastId)
                failedToastId = toastShow(t('Connection failed. Retrying...'), 'error', 0)
            }
            const delay = withJitter(FIXED_RECONNECT_INTERVAL, JITTER_RANGE)
            _scheduleReconnect(delay, 'reconnecting-fixed')
        }
    }
}

export const manualReconnect = () => {
    if (failedToastId !== null) {
        toastDismiss(failedToastId)
        failedToastId = null
    }
    wsAttempts = 0
    pendingReconnectOnVisible = false
    connectWebSocket()
}

export const disconnectWebSocket = () => {
    wsState.value = 'disconnected'
    hasConnectedOnce = false
    wsAttempts = 0
    pendingReconnectOnVisible = false
    clearTimeout(wsReconnectTimer)
    wsReconnectTimer = null
    _clearCountdown()
    clearInterval(pingInterval)
    onlineUsers.value = {}
    if (failedToastId !== null) {
        toastDismiss(failedToastId)
        failedToastId = null
    }
    if (ws) {
        ws.onclose = null
        ws.onerror = null
        try {
            ws.close()
        } catch (_) {
        }
        ws = null
    }
}

export const sendChatMessage = () => {
    if (!hasPermission('chat')) return
    if (chatInput.value.trim()) {
        _wsSend({action: 'chat', message: chatInput.value})
        chatInput.value = ''
    }
}

export const cleanupRealtime = () => {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    clearTimeout(wsReconnectTimer)
    _clearCountdown()
    clearInterval(pingInterval)
    if (ws) {
        try {
            ws.close()
        } catch (_) {
        }
    }
}