/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import {ref} from 'vue'

export const isDark = ref(localStorage.getItem('lexisync-theme') === 'dark')
export const showFab = ref(false)
export const loading = ref(false)
export const toasts = ref([])
export const isHistoryOpen = ref(false)
export const isShortcutsOpen = ref(false)
export const isNavMenuOpen = ref(false)

let toastSeq = 0

export const applyTheme = (dark) => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('lexisync-theme', dark ? 'dark' : 'light')
}
export const toggleTheme = () => {
    isDark.value = !isDark.value;
    applyTheme(isDark.value)
}

/**
 * 显示一条 Toast 消息。
 *
 * @param {string}      message     消息文本
 * @param {string}      type        'info' | 'success' | 'warning' | 'error'
 * @param {number}      duration    自动消失毫秒数；0 = 永不自动消失
 * @param {string|null} dedupeKey   去重键
 */
export const toastShow = (message, type = 'info', duration = 3000, dedupeKey = null) => {
    // ── 去重：原地更新 ───────────────────────────────────────────
    if (dedupeKey) {
        const existing = toasts.value.find(x => x.dedupeKey === dedupeKey && !x.leaving)
        if (existing) {
            existing.message = message
            existing.type = type
            existing.duration = duration

            if (existing._timerId) clearTimeout(existing._timerId)
            existing.remaining = duration
            existing._startTime = existing.paused ? null : Date.now()
            existing._timerId = (duration > 0 && !existing.paused)
                ? setTimeout(() => toastDismiss(existing.id), duration)
                : null

            existing.timerKey++

            // 轻微更新动效
            if (existing._nudgeTimer) clearTimeout(existing._nudgeTimer)
            existing.nudge = true
            existing._nudgeTimer = setTimeout(() => {
                existing.nudge = false
                existing._nudgeTimer = null
            }, 420)
            return existing.id
        }
    }

    // ── 新建 ────────────────────────────────────────────────────
    const id = ++toastSeq
    const timerId = duration > 0 ? setTimeout(() => toastDismiss(id), duration) : null
    const MAX_TOASTS = 5
    if (toasts.value.filter(x => !x.leaving).length >= MAX_TOASTS) {
        // 关掉最早的非持久 toast 
        const oldest = toasts.value.find(x => !x.leaving && x.duration > 0)
        if (oldest) toastDismiss(oldest.id)
    }
    toasts.value.push({
        id,
        message,
        type,
        leaving: false,
        dedupeKey: dedupeKey ?? null,
        duration,
        remaining: duration,
        paused: false,
        nudge: false,
        settled: false,
        timerKey: 0,
        _timerId: timerId,
        _startTime: duration > 0 ? Date.now() : null,
        _nudgeTimer: null,
    })
    setTimeout(() => {
        const t = toasts.value.find(x => x.id === id)
        if (t) t.settled = true
    }, 350)
    return id
}

export const toastPause = (id) => {
    const item = toasts.value.find(x => x.id === id)
    if (!item || item.paused || item.duration <= 0 || item.leaving) return

    const elapsed = item._startTime ? (Date.now() - item._startTime) : 0
    item.remaining = Math.max(80, item.remaining - elapsed)
    item._startTime = null
    item.paused = true

    if (item._timerId) {
        clearTimeout(item._timerId)
        item._timerId = null
    }
}

export const toastResume = (id) => {
    const item = toasts.value.find(x => x.id === id)
    if (!item || !item.paused || item.duration <= 0 || item.leaving) return

    item.paused = false
    item._startTime = Date.now()
    item._timerId = setTimeout(() => toastDismiss(item.id), item.remaining)
}

export const toastDismiss = (id) => {
    const item = toasts.value.find(x => x.id === id)
    if (!item) return
    if (item._timerId) {
        clearTimeout(item._timerId)
        item._timerId = null
    }
    if (item._nudgeTimer) {
        clearTimeout(item._nudgeTimer);
        item._nudgeTimer = null
    }
    item.leaving = true
    setTimeout(() => {
        toasts.value = toasts.value.filter(x => x.id !== id)
    }, 280)
}

export const toastDismissByKey = (dedupeKey) => {
    const item = toasts.value.find(x => x.dedupeKey === dedupeKey && !x.leaving)
    if (item) toastDismiss(item.id)
}

export const scrollToTop = () => window.scrollTo({top: 0, behavior: 'smooth'})
export const avatarColor = (name) => {
    const P = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16']
    let h = 0
    for (const c of (name || '?')) h = ((h * 31) + c.charCodeAt(0)) >>> 0
    return P[h % P.length]
}

// 时间戳格式化
export const formatTime = (iso, tFn = (k) => k) => {
    if (!iso) return ''
    const d = new Date(iso)
    const now = new Date()
    const diff = Math.max(0, Math.floor((now - d) / 1000))

    if (diff < 60) return tFn('Just now')
    if (diff < 3600) return `${Math.floor(diff / 60)}${tFn('m ago')}`

    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const yesterday = new Date(today.getTime() - 86400000)

    const pad = (n) => String(n).padStart(2, '0')
    const timeStr = `${pad(d.getHours())}:${pad(d.getMinutes())}`

    if (d >= today) return `${tFn('Today')} ${timeStr}`
    if (d >= yesterday) return `${tFn('Yesterday')} ${timeStr}`

    if (d.getFullYear() === now.getFullYear()) {
        return `${d.getMonth() + 1}-${pad(d.getDate())} ${timeStr}`
    }
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

applyTheme(isDark.value)