/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import {ref, computed, nextTick} from 'vue'
import {sessionToken, currentUser, t, checkSessionAndInit} from './auth.js'
import {tableData, globalActiveEditors, fetchProjectStats, activeRowId} from './project.js'
import {toastShow} from './ui.js'
import {registerWsSend} from './wsClient.js'

export const wsState = ref('disconnected')
export const wsStateLabel = computed(() => ({
    connecting: 'Connecting...',
    connected: 'Connected',
    reconnecting: 'Reconnecting...',
    disconnected: 'Disconnected',
    failed: 'Connection failed'
}[wsState.value] || ''))

export const onlineUsers = ref({})
export const onlineUsersArray = computed(() =>
    Object.entries(onlineUsers.value).map(([name, d]) => ({name, ...d}))
)

export const isChatOpen = ref(false)
export const chatMessages = ref([])
export const chatInput = ref('')

let ws = null
let wsReconnectTimer = null
let wsAttempts = 0
const MAX_WS_RETRY = 8
const INITIAL_RECONNECT_DELAY = 2000

const _wsSend = (obj) => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj))
}
registerWsSend(_wsSend)
export const wsSend = _wsSend

export const rebuildOnlineUsers = (list) => {
    if (!Array.isArray(list)) return
    const onlineNames = list.map(u => u.name)
    const next = {}
    for (const u of list) next[u.name] = {role: u.role, editingId: onlineUsers.value[u.name]?.editingId ?? null}
    onlineUsers.value = next
    for (const id in globalActiveEditors) {
        globalActiveEditors[id] = globalActiveEditors[id].filter(n => onlineNames.includes(n))
        const item = tableData.value.find(r => String(r.id) === String(id))
        if (item) item.active_editors = globalActiveEditors[id]
    }
}

export const fetchOnlineUsers = async () => {
    try {
        const res = await fetch(`/api/v1/users?token=${sessionToken.value}`, {cache: 'no-store'})
        if (res.ok) rebuildOnlineUsers((await res.json()).users || [])
    } catch (_) {
    }
}

const handleWsMsg = (msg) => {
    switch (msg.type) {
        case 'DATA_UPDATE': {
            const item = tableData.value.find(r => r.id === msg.data.ts_id)
            if (item) {
                if (msg.data.new_text != null) {
                    if (activeRowId.value === item.id && msg.data.user !== currentUser.name)
                        toastShow(`⚠️ ${msg.data.user || t('Someone')} ${t('just updated this entry. Your changes will overwrite theirs on save.')}`, 'warning', 5000)
                    else if (item.is_plural) item.plural_translations[msg.data.plural_index] = msg.data.new_text
                    else item.translation = msg.data.new_text
                }
                if (msg.data.is_reviewed != null) item.is_reviewed = msg.data.is_reviewed
                if (msg.data.is_fuzzy != null) item.is_fuzzy = msg.data.is_fuzzy
            }
            fetchProjectStats()
            break
        }
        case 'FOCUS_UPDATE': {
            const editors = globalActiveEditors[msg.data.ts_id] ?? (globalActiveEditors[msg.data.ts_id] = [])
            if (msg.data.status === 'editing') {
                if (!editors.includes(msg.data.user)) editors.push(msg.data.user)
            } else globalActiveEditors[msg.data.ts_id] = editors.filter(u => u !== msg.data.user)
            const item = tableData.value.find(r => r.id === msg.data.ts_id)
            if (item) item.active_editors = globalActiveEditors[msg.data.ts_id]
            if (onlineUsers.value[msg.data.user] !== undefined)
                onlineUsers.value[msg.data.user].editingId = msg.data.status === 'editing' ? msg.data.ts_id : null
            break
        }
        case 'USER_CONNECTED':
        case 'USER_DISCONNECTED':
            rebuildOnlineUsers(msg.data.online_users)
            break
        case 'CHAT_MESSAGE':
            chatMessages.value.push(msg.data)
            if (!isChatOpen.value) toastShow(`${msg.data.user}: ${msg.data.text}`, 'info', 3000)
            nextTick(() => {
                const el = document.getElementById('chatMessages');
                if (el) el.scrollTop = el.scrollHeight
            })
            break
    }
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
            wsState.value = 'disconnected';
            checkSessionAndInit();
            return
        }
        if (++wsAttempts > MAX_WS_RETRY) {
            wsState.value = 'failed';
            toastShow(t('Connection failed'), 'error', 0);
            return
        }
        const delay = Math.min(INITIAL_RECONNECT_DELAY * 2 ** (wsAttempts - 1), 30000)
        wsState.value = 'reconnecting'
        toastShow(`${t('Reconnecting...')} (${wsAttempts}/${MAX_WS_RETRY})`, 'warning', delay - 200)
        wsReconnectTimer = setTimeout(connectWebSocket, delay)
    }
}

export const disconnectWebSocket = () => {
    wsState.value = 'disconnected'
    clearTimeout(wsReconnectTimer)
    onlineUsers.value = {}
    if (ws) {
        try {
            ws.close()
        } catch (_) {
        }
        ws = null
    }
}

export const sendChatMessage = () => {
    if (chatInput.value.trim()) {
        _wsSend({action: 'chat', message: chatInput.value});
        chatInput.value = ''
    }
}

export const cleanupRealtime = () => {
    clearTimeout(wsReconnectTimer)
    if (ws) {
        try {
            ws.close()
        } catch (_) {
        }
    }
}