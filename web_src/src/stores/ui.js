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

let toastSeq = 0

export const applyTheme = (dark) => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('lexisync-theme', dark ? 'dark' : 'light')
}
export const toggleTheme = () => {
    isDark.value = !isDark.value;
    applyTheme(isDark.value)
}

export const toastShow = (message, type = 'info', duration = 3000) => {
    const id = ++toastSeq
    toasts.value.push({id, message, type, leaving: false})
    if (duration > 0) setTimeout(() => toastDismiss(id), duration)
    return id
}
export const toastDismiss = (id) => {
    const item = toasts.value.find(x => x.id === id)
    if (!item) return
    item.leaving = true
    setTimeout(() => {
        toasts.value = toasts.value.filter(x => x.id !== id)
    }, 280)
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
    const diff = Math.max(0, Math.floor((now - d) / 1000)) // 相差秒数

    // 1分钟内
    if (diff < 60) return tFn('Just now')
    // 1小时内
    if (diff < 3600) return `${Math.floor(diff / 60)}${tFn('m ago')}`
    
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const yesterday = new Date(today.getTime() - 86400000)

    const pad = (n) => String(n).padStart(2, '0')
    const timeStr = `${pad(d.getHours())}:${pad(d.getMinutes())}`

    // 今天
    if (d >= today) return `${tFn('Today')} ${timeStr}`
    // 昨天
    if (d >= yesterday) return `${tFn('Yesterday')} ${timeStr}`

    // 今年
    if (d.getFullYear() === now.getFullYear()) {
        return `${d.getMonth() + 1}-${pad(d.getDate())} ${timeStr}`
    }
    // 更早
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

applyTheme(isDark.value)