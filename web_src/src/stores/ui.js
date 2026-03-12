/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import {ref} from 'vue'

export const isDark = ref(localStorage.getItem('lexisync-theme') === 'dark')
export const showFab = ref(false)
export const loading = ref(false)
export const toasts = ref([])

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
export const formatTime = (iso) => {
    const d = new Date(iso)
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

applyTheme(isDark.value)