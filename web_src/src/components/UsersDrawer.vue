<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <Teleport to="body">
    <transition name="fade">
      <div v-if="isUsersOpen" class="users-mask" @click="isUsersOpen = false"></div>
    </transition>
    <div :class="['users-drawer', { open: isUsersOpen }]">
      <div class="users-header">
        <div class="header-title">
          <el-icon><User /></el-icon>
          <span>{{ t('Online Users') }} ({{ sortedUsers.length }})</span>
        </div>
        <div class="header-actions">
          <el-button :icon="Close" link @click="isUsersOpen = false"></el-button>
        </div>
      </div>

      <div class="users-content">
        <div 
          v-for="u in sortedUsers" 
          :key="u.name" 
          :class="['user-item', { 'is-me': u.name === currentUser.name }]"
        >
          <div class="user-avatar" :style="{ background: avatarColor(u.name) }">
            {{ (u.name || '?')[0].toUpperCase() }}
          </div>
          
          <div class="user-info">
            <div class="user-name-row">
              <span class="u-name">{{ u.name }}</span>
              <el-tag size="small" type="info" class="role-tag">{{ t(u.role) }}</el-tag>
              <el-tag v-if="u.name === currentUser.name" size="small" type="primary" class="me-tag">{{ t('You') }}</el-tag>
            </div>
            
            <div class="u-status editing" v-if="u.editing_ts_id" @click="jumpToItem(u.editing_ts_id)">
              <span class="status-dot green"></span>
              <span class="status-text">{{ t('Editing...') }}</span>
            </div>
            <div class="u-status idle" v-else>
              <span class="status-dot gray"></span>
              <span class="status-text">{{ t('Idle') }}</span>
            </div>
          </div>

          <div class="user-actions" v-if="currentUser.role === 'admin' && u.name !== currentUser.name">
            <el-dropdown trigger="click" @command="(cmd) => handleAction(cmd, u)">
              <el-button circle size="small" :icon="MoreFilled" class="action-btn"></el-button>
              <template #dropdown>
                <el-dropdown-menu class="custom-nav-dropdown">
                  <el-dropdown-item command="kick" :icon="Close">{{ t('Kick User') }}</el-dropdown-item>
                  <el-dropdown-item command="ban" :icon="Remove" divided class="logout-item">{{ t('Ban IP') }}</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { User, Close, MoreFilled, Remove } from '@element-plus/icons-vue'
import { t, currentUser } from '../stores/auth.js'
import { isUsersOpen, onlineUsersArray, kickUser, banUserIp } from '../stores/realtime.js'
import { itemToFocus } from '../stores/project.js'
import { avatarColor } from '../stores/ui.js'

// 将自己置顶
const sortedUsers = computed(() => {
  const users = [...onlineUsersArray.value]
  const meIdx = users.findIndex(u => u.name === currentUser.name)
  if (meIdx > -1) {
    const [me] = users.splice(meIdx, 1)
    users.unshift(me)
  }
  return users
})

const handleAction = (command, user) => {
  if (command === 'kick') kickUser(user.name)
  if (command === 'ban') banUserIp(user.ip, user.name)
}

const jumpToItem = (ts_id) => {
  isUsersOpen.value = false
  setTimeout(() => { itemToFocus.value = ts_id }, 250)
}
</script>

<style scoped>
.users-mask {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
  background: rgba(0, 0, 0, 0.3); z-index: 1900;
}
.users-drawer {
  position: fixed; top: 0; bottom: 0; right: 0; width: 380px;
  background: var(--card-bg); border-left: 1px solid var(--border);
  box-shadow: -5px 0 20px rgba(0,0,0,0.1); z-index: 2000;
  display: flex; flex-direction: column;
  transform: translateX(100%); transition: transform 0.3s cubic-bezier(0.7, 0.3, 0.1, 1);
  visibility: hidden;
}
.users-drawer.open { transform: translateX(0); visibility: visible; }
.users-header {
  padding: 15px 20px; height: var(--navbar-h); border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center;
}
.header-title { display: flex; align-items: center; gap: 8px; font-weight: 600; color: var(--text-main); }
.users-content { flex: 1; overflow-y: auto; background: var(--bg-main); }

.user-item {
  display: flex; align-items: center; gap: 12px; padding: 14px 20px;
  background: var(--card-bg); border-bottom: 1px solid var(--border);
  position: relative; transition: background 0.2s;
}
.user-item:hover { background: var(--hover-bg); }
.user-item.is-me { background: var(--hover-bg); border-left: 3px solid #409EFF; padding-left: 17px; }

.user-avatar {
  width: 36px; height: 36px; border-radius: 50%; color: #fff; font-size: 14px;
  font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}

.user-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.user-name-row { display: flex; align-items: center; gap: 6px; }
.u-name { font-size: 14px; font-weight: 600; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 140px; }
.role-tag { zoom: 0.85; }
.me-tag { zoom: 0.85; }

.u-status { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); }
.u-status.editing { color: #10b981; cursor: pointer; }
.u-status.editing:hover .status-text { text-decoration: underline; }

.status-dot { width: 6px; height: 6px; border-radius: 50%; }
.status-dot.green { background: #10b981; animation: pulse 1.5s infinite; }
.status-dot.gray { background: #94a3b8; }

.user-actions { opacity: 0; transition: opacity 0.2s; }
.user-item:hover .user-actions { opacity: 1; }

@media (max-width: 768px) {
  .users-drawer { width: 85%; max-width: 100%; }
  .user-actions { opacity: 1; } /* 移动端常驻显示 */
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>