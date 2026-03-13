<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <Teleport to="body">
    <transition name="fade">
      <div v-if="isChatOpen" class="chat-mask" @click="isChatOpen = false"></div>
    </transition>
    <div :class="['chat-drawer', { open: isChatOpen }]">
      <div class="chat-header">
        <div class="header-title">
          <el-icon>
            <ChatDotRound/>
          </el-icon>
          <span>{{ t('Chat') }}</span>
        </div>
        <el-button :icon="Close" link @click="isChatOpen = false"></el-button>
      </div>

      <div id="chatMessages" class="chat-messages">
        <div v-for="(msg, i) in chatMessages" :key="i"
             :class="['chat-msg', msg.user === currentUser.name ? 'self' : 'other']">
          <div class="chat-meta">{{ msg.user }} ({{ t(msg.role) }}) • {{ formatTime(msg.time) }}</div>
          <div class="chat-bubble">{{ msg.text }}</div>
        </div>
      </div>

      <!-- ── Input area: shown only when the user has the chat permission ── -->
      <div class="chat-input-area" v-if="hasPermission('chat')">
        <el-input v-model="chatInput" :placeholder="t('Type a message...')" @keyup.enter="sendChatMessage"></el-input>
        <el-button :icon="Position" type="primary" @click="sendChatMessage"></el-button>
      </div>

      <!-- ── No-permission notice ── -->
      <div class="chat-no-perm" v-else>
        <el-icon>
          <Lock/>
        </el-icon>
        <span>{{ t('No chat permission') }}</span>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import {Close, Position, ChatDotRound, Lock} from '@element-plus/icons-vue'
import {currentUser, t, hasPermission} from '../stores/auth.js'
import {isChatOpen, chatMessages, chatInput, sendChatMessage} from '../stores/realtime.js'
import {formatTime} from '../stores/ui.js'
</script>

<style scoped>
.chat-mask {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.3);
  z-index: 1900;
}

.chat-drawer {
  position: fixed;
  top: 0;
  bottom: 0;
  right: 0;
  width: 380px;
  background: var(--card-bg);
  border-left: 1px solid var(--border);
  box-shadow: -5px 0 20px rgba(0, 0, 0, 0.1);
  z-index: 2000;
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.3s cubic-bezier(0.7, 0.3, 0.1, 1);
  visibility: hidden;
}

.chat-drawer.open {
  transform: translateX(0);
  visibility: visible;
}

.chat-header {
  padding: 15px 20px;
  height: var(--navbar-h);
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--text-main);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-msg {
  display: flex;
  flex-direction: column;
  max-width: 85%;
}

.chat-msg.self {
  align-self: flex-end;
}

.chat-msg.other {
  align-self: flex-start;
}

.chat-meta {
  font-size: 10px;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.chat-msg.self .chat-meta {
  text-align: right;
}

.chat-bubble {
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.4;
  word-break: break-word;
}

.chat-msg.self .chat-bubble {
  background: #409EFF;
  color: #fff;
  border-bottom-right-radius: 2px;
}

.chat-msg.other .chat-bubble {
  background: var(--bg-main);
  color: var(--text-main);
  border-bottom-left-radius: 2px;
}

/* ── Active input area ───────────────────────────────────────────────────── */
.chat-input-area {
  padding: 15px;
  padding-bottom: calc(15px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--border);
  background: var(--card-bg);
  display: flex;
  gap: 8px;
}

/* ── No-permission notice ─────────────────────────────────────────────────── */
.chat-no-perm {
  padding: 14px 20px;
  padding-bottom: calc(14px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--border);
  background: var(--card-bg-alt);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  user-select: none;
}

/* 移动端 */
@media (max-width: 768px) {
  .chat-drawer {
    width: 85%;
    max-width: 100%;
  }
}

/* 动画 */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>