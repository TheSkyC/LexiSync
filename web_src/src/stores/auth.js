/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import { ref, reactive } from 'vue'
import { loading } from './ui.js'
import { fetchData } from './project.js'
import { connectWebSocket, disconnectWebSocket } from './realtime.js'

const checkInitialAuth = () => {
  if (new URLSearchParams(window.location.search).get('token')) return false
  return !!sessionStorage.getItem('cloud_session')
}

export const showAuthDialog = ref(!checkInitialAuth())
export const authTab        = ref('account')
export const authError      = ref('')
export const loginForm      = reactive({ username: '', password: '' })
export const tokenForm      = reactive({ token: '', displayName: '' })
export const rememberMe     = ref(true)
export const sessionToken   = ref('')
// permissions: string[] — effective permission keys from /api/v1/me
// scope: { languages: string[]|null, files: string[]|null } | null
export const currentUser    = reactive({ name: '', role: 'viewer', permissions: [], scope: null })
export const i18n           = ref({})

export const t = (key) => i18n.value[key] || key

export const hasPermission = (perm) => currentUser.permissions.includes(perm)

export const authFetch = (url, options = {}) => {
  const separator = url.includes('?') ? '&' : '?'
  const finalUrl = `${url}${separator}token=${sessionToken.value}`
  return fetch(finalUrl, options)
}

export const saveSession = (token) => {
  sessionToken.value = token
  sessionStorage.setItem('cloud_session', token)
}

export const initApp = async () => {
  loading.value = true
  try {
    const res = await authFetch('/api/v1/i18n', { cache: 'no-store' })
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
  currentUser.name        = data.name
  currentUser.role        = data.role
  currentUser.permissions = Array.isArray(data.permissions) ? data.permissions : []
  currentUser.scope       = data.scope ?? null
  await initApp() // 登录成功后直接调用初始化
}

const fetchMe = async () => {
  const res = await authFetch('/api/v1/me', { cache: 'no-store' })
  if (!res.ok) throw new Error('Session verification failed')
  return res.json()
}

export const loginAccount = async () => {
  if (!loginForm.username || !loginForm.password) { authError.value = 'Fill all fields'; return }
  loading.value = true; authError.value = ''
  try {
    const res = await fetch('/api/v1/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(loginForm)
    })
    if (!res.ok) throw new Error('Invalid credentials')
    const data = await res.json()
    saveSession(data.token)
      
    const meData = await fetchMe()

    if (rememberMe.value) {
      localStorage.setItem('lexisync_auth', JSON.stringify({
        type: 'account', username: loginForm.username, password: btoa(loginForm.password)
      }))
    } else {
      localStorage.removeItem('lexisync_auth')
    }
    await afterLogin(meData)
  } catch (e) { authError.value = e.message }
  finally { loading.value = false }
}

export const loginToken = async () => {
  if (!tokenForm.token) { authError.value = 'Token required'; return }
  loading.value = true; authError.value = ''
  try {
    const res = await fetch('/api/v1/login-token', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: tokenForm.token, display_name: tokenForm.displayName })
    })
    if (!res.ok) throw new Error('Invalid or expired token')
    const data = await res.json()
    saveSession(data.token)
      
    const meData = await fetchMe()

    if (rememberMe.value) {
      localStorage.setItem('lexisync_auth', JSON.stringify({
        type: 'token',
        token: tokenForm.token,
        displayName: tokenForm.displayName
      }))
    } else {
      localStorage.removeItem('lexisync_auth')
    }
    await afterLogin(meData)
  } catch (e) { authError.value = e.message }
  finally { loading.value = false }
}

export const checkSessionAndInit = async () => {
  const existing = sessionStorage.getItem('cloud_session')
  const saved    = localStorage.getItem('lexisync_auth')

  if (existing || saved) loading.value = true

  if (existing) {
    sessionToken.value = existing
    try {
      const res = await authFetch('/api/v1/me', { cache: 'no-store' })
      if (res.ok) { await afterLogin(await res.json()); return }
    } catch (_) {}
  }

  if (saved) {
    try {
      const auth = JSON.parse(saved)
      if (auth.type === 'account') {
        loginForm.username = auth.username; loginForm.password = atob(auth.password); rememberMe.value = true
        await loginAccount(); return
      }
      if (auth.type === 'token') {
        tokenForm.token = auth.token; tokenForm.displayName = auth.displayName; rememberMe.value = true
        await loginToken(); return
      }
    } catch (_) { localStorage.removeItem('lexisync_auth') }
  }

  loading.value = false
  showAuthDialog.value = true
}