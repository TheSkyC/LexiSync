/*
 * Copyright (c) 2025-2026, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import {ref, reactive} from 'vue'
import {loading} from './ui.js'
import {fetchData} from './project.js'
import {connectWebSocket, disconnectWebSocket} from './realtime.js'

const checkInitialAuth = () => {
    if (new URLSearchParams(window.location.search).get('token')) return false
    return !!sessionStorage.getItem('cloud_session')
}

export const showAuthDialog = ref(!checkInitialAuth())
export const authTab = ref('account')
export const authError = ref('')
export const loginForm = reactive({username: '', password: ''})
export const tokenForm = reactive({token: '', displayName: ''})
export const rememberMe = ref(true)
export const sessionToken = ref('')
export const currentUser = reactive({name: '', role: 'viewer', permissions: [], scope: null})
export const i18n = ref({})

export const t = (key) => i18n.value[key] || key

export const hasPermission = (perm) => currentUser.permissions.includes(perm)

export const authFetch = (url, options = {}) => {
    const headers = new Headers(options.headers || {})
    if (sessionToken.value) {
        headers.set('Authorization', `Bearer ${sessionToken.value}`)
    }
    return fetch(url, {...options, headers})
}

export const saveSession = (token) => {
    sessionToken.value = token
    sessionStorage.setItem('cloud_session', token)
}

export const initApp = async () => {
    loading.value = true
    try {
        const res = await authFetch('/api/v1/i18n', {cache: 'no-store'})
        if (res.ok) i18n.value = await res.json()
        await fetchData()
        showAuthDialog.value = false
        connectWebSocket()
    } catch (_) {
        authError.value = 'Failed to initialize app.'
    } finally {
        loading.value = false
    }
}

export const logout = () => {
    sessionStorage.removeItem('cloud_session')
    localStorage.removeItem('lexisync_auth')
    sessionToken.value = ''
    disconnectWebSocket()
    showAuthDialog.value = true
}

const afterLogin = async (data) => {
    currentUser.name = data.name
    currentUser.role = data.role
    currentUser.permissions = Array.isArray(data.permissions) ? data.permissions : []
    currentUser.scope = data.scope ?? null
    await initApp()
}

const fetchMe = async () => {
    const res = await authFetch('/api/v1/me', {cache: 'no-store'})
    if (!res.ok) throw new Error('Session verification failed')
    return res.json()
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
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(loginForm)
        })
        if (!res.ok) throw new Error('Invalid credentials')
        const data = await res.json()
        saveSession(data.token)
        
        if (rememberMe.value) {
            localStorage.setItem('lexisync_auth', JSON.stringify({
                type: 'account', remember_token: data.remember_token
            }))
        } else {
            localStorage.removeItem('lexisync_auth')
        }
        await afterLogin(await fetchMe())
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
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({token: tokenForm.token, display_name: tokenForm.displayName})
        })
        if (!res.ok) throw new Error('Invalid or expired token')
        const data = await res.json()
        saveSession(data.token)

        if (rememberMe.value) {
            localStorage.setItem('lexisync_auth', JSON.stringify({
                type: 'token', token: tokenForm.token, displayName: tokenForm.displayName
            }))
        } else {
            localStorage.removeItem('lexisync_auth')
        }
        await afterLogin(await fetchMe())
    } catch (e) {
        authError.value = e.message
    } finally {
        loading.value = false
    }
}

export const checkSessionAndInit = async () => {
    const existing = sessionStorage.getItem('cloud_session')
    const saved = localStorage.getItem('lexisync_auth')

    if (existing || saved) loading.value = true

    // 1. 尝试 URL 中的 Token (快速分享)
    const urlParams = new URLSearchParams(window.location.search)
    const urlToken = urlParams.get('token')
    if (urlToken) {
        const cleanUrl = new URL(window.location.href)
        cleanUrl.searchParams.delete('token')
        window.history.replaceState({}, document.title, cleanUrl.pathname + cleanUrl.search + cleanUrl.hash)

        sessionToken.value = urlToken
        try {
            const res = await authFetch('/api/v1/me', {cache: 'no-store'})
            if (res.ok) {
                await afterLogin(await res.json());
                return
            }
        } catch (_) {
        }
    }

    // 2. 尝试现有 Session
    if (existing) {
        sessionToken.value = existing
        try {
            const res = await authFetch('/api/v1/me', {cache: 'no-store'})
            if (res.ok) {
                await afterLogin(await res.json());
                return
            }
        } catch (_) {
        }
    }

    // 3. 尝试安全的 Remember Token
    if (saved) {
        try {
            const auth = JSON.parse(saved)
            if (auth.type === 'account' && auth.remember_token) {
                const res = await fetch('/api/v1/login-remembered', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({remember_token: auth.remember_token})
                })
                if (res.ok) {
                    const data = await res.json()
                    saveSession(data.token)
                    await afterLogin(await fetchMe())
                    return
                }
            }
            if (auth.type === 'token') {
                tokenForm.token = auth.token;
                tokenForm.displayName = auth.displayName;
                rememberMe.value = true
                await loginToken();
                return
            }
        } catch (_) {
            localStorage.removeItem('lexisync_auth')
        }
    }

    loading.value = false
    showAuthDialog.value = true
}