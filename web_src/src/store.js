/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import { sessionToken, showAuthDialog, authError, i18n, registerLoginSuccessHandler, authFetch } from './stores/auth.js'
import { fetchData, cleanupProject } from './stores/project.js'
import { connectWebSocket, disconnectWebSocket, cleanupRealtime } from './stores/realtime.js'
import { loading } from './stores/ui.js'

const initApp = async () => {
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

registerLoginSuccessHandler(initApp)

export const logout = () => {
  sessionStorage.removeItem('cloud_session')
  localStorage.removeItem('lexisync_auth')
  sessionToken.value = ''
  disconnectWebSocket()
  showAuthDialog.value = true
}

export const cleanupStore = () => {
  cleanupProject()
  cleanupRealtime()
}

export * from './stores/ui.js'
export * from './stores/auth.js'
export * from './stores/project.js'
export * from './stores/realtime.js'