/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import { ref, reactive } from 'vue'
import { loading } from './ui.js'

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
export const currentUser    = reactive({ name: '', role: 'viewer' })
export const i18n           = ref({})

export const t = (key) => i18n.value[key] || key

export const saveSession = (token) => {
  sessionToken.value = token
  sessionStorage.setItem('cloud_session', token)
}

// store.js（组合根）在加载时注册 initApp，避免循环依赖
let _onLoginSuccess = null
export const registerLoginSuccessHandler = (fn) => { _onLoginSuccess = fn }

const afterLogin = async (data) => {
  currentUser.name = data.name
  currentUser.role = data.role
  await _onLoginSuccess?.()
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
    if (rememberMe.value) {
      localStorage.setItem('lexisync_auth', JSON.stringify({
        type: 'account', username: loginForm.username, password: btoa(loginForm.password)
      }))
    } else { localStorage.removeItem('lexisync_auth') }
    await afterLogin(data)
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
    if (rememberMe.value) {
      localStorage.setItem('lexisync_auth', JSON.stringify({
        type: 'token', token: tokenForm.token, displayName: tokenForm.displayName
      }))
    } else { localStorage.removeItem('lexisync_auth') }
    await afterLogin(data)
  } catch (e) { authError.value = e.message }
  finally { loading.value = false }
}

export const checkSessionAndInit = async () => {
  const existing = sessionStorage.getItem('cloud_session')
  const saved    = localStorage.getItem('lexisync_auth')

  // 有凭据就先显示 loading，避免空白闪烁
  if (existing || saved) loading.value = true

  if (existing) {
    sessionToken.value = existing
    try {
      const res = await fetch(`/api/v1/me?token=${sessionToken.value}`, { cache: 'no-store' })
      if (res.ok) { await afterLogin(await res.json()); return }
    } catch (_) {}
  }

  if (saved) {
    try {
      const auth = JSON.parse(saved)
      if (auth.type === 'account') {
        loginForm.username = auth.username; loginForm.password = atob(auth.password); rememberMe.value = true
        await loginAccount(); return  // loginAccount 的 finally 会重置 loading
      }
      if (auth.type === 'token') {
        tokenForm.token = auth.token; tokenForm.displayName = auth.displayName; rememberMe.value = true
        await loginToken(); return    // loginToken 的 finally 会重置 loading
      }
    } catch (_) { localStorage.removeItem('lexisync_auth') }
  }

  // 所有凭据均失败，重置 loading 并展示登录框
  loading.value = false
  showAuthDialog.value = true
}