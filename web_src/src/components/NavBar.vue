<!--
Copyright (c) 2025-2026, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <nav class="navbar">
    <div class="navbar-left">
      <h2 class="project-name">{{ project.name || 'LexiSync' }}</h2>
      <div class="lang-badge" v-if="project.source_lang">
        {{ project.source_lang }} <span class="sep">▶</span> {{ project.target_lang }}
      </div>
      <el-tag size="small" type="info" style="margin-left: 10px;">{{ t(currentUser.role) }}</el-tag>
      <el-tooltip v-if="hasScopeRestriction" :content="scopeDescription" placement="bottom" :show-after="300">
        <el-tag size="small" type="warning" class="scope-badge">
          <el-icon style="margin-right:3px;">
            <Lock/>
          </el-icon>
          {{ t('Scoped') }}
        </el-tag>
      </el-tooltip>
    </div>

    <div class="collab-wrap" v-if="onlineUsersArray.length" @click="isUsersOpen = true" style="cursor: pointer;">
      <el-tooltip v-for="u in onlineUsersArray.slice(0, 5)" :key="u.name" :content="u.name + ' (' + t(u.role) + ')'"
                  placement="bottom">
        <div class="collab-avatar" :style="{ background: avatarColor(u.name) }">{{
            (u.name || '?')[0].toUpperCase()
          }}
        </div>
      </el-tooltip>
      <span class="collab-count" v-if="onlineUsersArray.length > 5">+{{ onlineUsersArray.length - 5 }}</span>
      <span class="collab-count">{{ onlineUsersArray.length }} {{ t('online') }}</span>
    </div>

    <div class="navbar-right">
      <!-- WS 状态徽章：failed/reconnecting-fixed 状态下可点击手动重连 -->
      <el-tooltip
          :content="wsClickable ? t('Click to reconnect') : t(wsStateLabel)"
          placement="bottom"
          :show-after="300"
      >
        <div
            :class="['ws-status', `ws-${wsState}`, { 'ws-clickable': wsClickable }]"
            @click="handleWsClick"
        >
          <span class="ws-dot"></span>
          <span class="ws-label">{{ t(wsStateLabel) }}</span>
          <!-- 固定重连阶段显示倒计时 -->
          <span v-if="wsState === 'reconnecting-fixed' && wsReconnectCountdown > 0" class="ws-countdown">
            {{ wsReconnectCountdown }}s
          </span>
        </div>
      </el-tooltip>

      <div class="nav-actions">
        <el-badge :value="unreadChatCount" :max="99" :hidden="unreadChatCount === 0" class="chat-badge">
          <el-button :icon="ChatDotRound" @click="isChatOpen = !isChatOpen" circle :title="t('Chat')"></el-button>
        </el-badge>

        <!-- 刷新按钮：同时刷新数据并（在连接断开时）触发手动重连 -->
        <el-button
            type="primary"
            :icon="RefreshRight"
            @click="handleRefresh"
            circle
            :loading="loading"
            :title="t('Refresh')"
        ></el-button>

        <el-dropdown
            trigger="click"
            @command="handleCommand"
            @visible-change="(val) => isNavMenuOpen = val"
            placement="bottom-end"
        >
          <el-button circle class="more-btn" :title="t('More options')">
            <el-icon>
              <MoreFilled/>
            </el-icon>
          </el-button>

          <template #dropdown>
            <el-dropdown-menu class="custom-nav-dropdown">
              <el-dropdown-item command="users" :icon="User">
                {{ t('Online Users') }}
              </el-dropdown-item>
              <el-dropdown-item command="history" :icon="Clock">
                {{ t('Audit Log') }}
              </el-dropdown-item>
              <el-dropdown-item command="shortcuts" :icon="Key">
                {{ t('Keyboard Shortcuts') }}
              </el-dropdown-item>
              <el-dropdown-item command="theme" :icon="isDark ? Sunny : Moon">
                {{ t(isDark ? 'Light Mode' : 'Dark Mode') }}
              </el-dropdown-item>
              <el-dropdown-item divided command="logout" :icon="SwitchButton" class="logout-item">
                {{ t('Logout') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
  </nav>
</template>

<script setup>
import {computed} from 'vue'
import {
  ChatDotRound,
  RefreshRight,
  SwitchButton,
  Sunny,
  Moon,
  Lock,
  Clock,
  Key,
  MoreFilled,
  User
} from '@element-plus/icons-vue'
import {project, fetchData, fetchAuditHistory} from '../stores/project.js'
import {currentUser, logout, t} from '../stores/auth.js'
import {
  onlineUsersArray, wsState, wsStateLabel, wsReconnectCountdown,
  isChatOpen, unreadChatCount, isUsersOpen,
  manualReconnect
} from '../stores/realtime.js'
import {loading, isDark, toggleTheme, avatarColor, isHistoryOpen, isShortcutsOpen, isNavMenuOpen} from '../stores/ui.js'

const hasScopeRestriction = computed(() => {
  const s = currentUser.scope
  return !!(s && (s.languages?.length || s.files?.length))
})

const scopeDescription = computed(() => {
  const s = currentUser.scope
  if (!s) return ''
  const parts = []
  if (s.languages?.length) parts.push(`${t('Languages')}: ${s.languages.join(', ')}`)
  if (s.files?.length) parts.push(`${t('Files')}: ${s.files.join(', ')}`)
  return parts.join('\n') || t('Restricted scope')
})

const wsClickable = computed(() =>
    wsState.value === 'failed' ||
    wsState.value === 'reconnecting-fixed' ||
    wsState.value === 'disconnected'
)

const handleWsClick = () => {
  if (wsClickable.value) manualReconnect()
}

const handleRefresh = () => {
  fetchData()
  if (wsState.value !== 'connected' && wsState.value !== 'connecting') {
    manualReconnect()
  }
}

const openHistory = () => {
  isHistoryOpen.value = true
  fetchAuditHistory()
}

const handleCommand = (command) => {
  switch (command) {
    case 'users':
      isUsersOpen.value = true
      break
    case 'history':
      openHistory()
      break
    case 'shortcuts':
      isShortcutsOpen.value = true
      break
    case 'theme':
      toggleTheme()
      break
    case 'logout':
      logout()
      break
  }
}
</script>

<style scoped>
.navbar {
  height: var(--navbar-h);
  background: var(--card-bg);
  border-bottom: 1px solid var(--border);
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  z-index: 200;
  flex-shrink: 0;
}

.navbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.project-name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-main);
}

.lang-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-sec);
  background: var(--card-bg-alt);
  border: 1px solid var(--border);
  padding: 2px 9px;
  border-radius: 20px;
}

.lang-badge .sep {
  color: #409EFF;
  font-size: 9px;
}

.scope-badge {
  cursor: default;
  display: inline-flex;
  align-items: center;
}

.ws-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 20px;
  border: 1px solid transparent;
  transition: opacity 0.15s, transform 0.15s;
  user-select: none;
}

.ws-status.ws-clickable {
  cursor: pointer;
}

.ws-status.ws-clickable:hover {
  opacity: 0.8;
  transform: scale(1.04);
}

.ws-status.ws-clickable:active {
  transform: scale(0.97);
}

.ws-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.ws-countdown {
  font-size: 10px;
  font-weight: 600;
  margin-left: 2px;
  opacity: 0.75;
}

.ws-status.ws-connected {
  background: rgba(34, 197, 94, .1);
  color: #16a34a;
}

.ws-status.ws-connected .ws-dot {
  background: #22c55e;
}

.ws-status.ws-connecting {
  background: rgba(245, 158, 11, .1);
  color: #d97706;
}

.ws-status.ws-connecting .ws-dot {
  background: #f59e0b;
  animation: pulse 1.2s infinite;
}

.ws-status.ws-reconnecting {
  background: rgba(245, 158, 11, .1);
  color: #d97706;
}

.ws-status.ws-reconnecting .ws-dot {
  background: #f59e0b;
  animation: pulse 1.2s infinite;
}

.ws-status.ws-reconnecting-fixed {
  background: rgba(239, 68, 68, .08);
  color: #dc2626;
  border-color: rgba(239, 68, 68, .2);
}

.ws-status.ws-reconnecting-fixed .ws-dot {
  background: #ef4444;
  animation: pulse 2s infinite;
}

.ws-status.ws-disconnected {
  background: rgba(100, 116, 139, .1);
  color: #64748b;
}

.ws-status.ws-disconnected .ws-dot {
  background: #94a3b8;
}

.ws-status.ws-failed {
  background: rgba(239, 68, 68, .1);
  color: #dc2626;
}

.ws-status.ws-failed .ws-dot {
  background: #ef4444;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: .35;
  }
}

.collab-wrap {
  display: flex;
  align-items: center;
  gap: 2px;
}

.collab-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--card-bg);
  margin-left: -6px;
  transition: transform .2s;
}

.collab-avatar:first-child {
  margin-left: 0;
}

.collab-avatar:hover {
  transform: translateY(-3px);
  z-index: 10;
}

.collab-count {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: 4px;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-badge {
  display: inline-flex;
}

.chat-badge :deep(.el-badge__content.is-fixed) {
  top: 4px;
  right: 4px;
  transform: translateY(-50%) translateX(50%) scale(0.85);
}

.more-btn {
  transition: transform 0.2s ease, background-color 0.2s;
}

.more-btn:hover {
  transform: rotate(90deg);
}

:global(.custom-nav-dropdown) {
  border-radius: 8px !important;
  padding: 4px !important;
}

:global(.custom-nav-dropdown .logout-item) {
  color: var(--st-untranslated, #ef4444) !important;
  font-weight: 500;
}

:global(.custom-nav-dropdown .logout-item:hover) {
  background-color: rgba(239, 68, 68, 0.08) !important;
  color: #dc2626 !important;
}

html.dark :global(.custom-nav-dropdown .logout-item:hover) {
  background-color: rgba(239, 68, 68, 0.15) !important;
  color: #f87171 !important;
}

@media (max-width: 768px) {
  .navbar {
    padding: 0 10px;
    gap: 4px;
    flex-wrap: nowrap;
  }

  .project-name {
    max-width: 80px;
    font-size: 15px;
  }

  .lang-badge {
    display: none;
  }

  .scope-badge :deep(.el-tag__content) {
    display: none;
  }

  .ws-label {
    display: none;
  }

  .ws-status.ws-reconnecting-fixed .ws-countdown {
    display: inline;
  }

  .ws-status {
    padding: 3px 6px;
  }

  .collab-count {
    display: none;
  }

  .nav-actions {
    gap: 4px;
  }

  .nav-actions :deep(.el-button) {
    padding: 5px;
    margin: 0;
  }
}
</style>