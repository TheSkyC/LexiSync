<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div :class="['chat-drawer', { open: isChatOpen }]">
    <div class="chat-header">
      <span>{{ t('Chat') }}</span>
      <el-button :icon="Close" link @click="isChatOpen = false"></el-button>
    </div>
    <div id="chatMessages" class="chat-messages">
      <div v-for="(msg, i) in chatMessages" :key="i"
           :class="['chat-msg', msg.user === currentUser.name ? 'self' : 'other']">
        <div class="chat-meta">{{ msg.user }} ({{ t(msg.role) }}) • {{ formatTime(msg.time) }}</div>
        <div class="chat-bubble">{{ msg.text }}</div>
      </div>
    </div>
    <div class="chat-input-area">
      <el-input v-model="chatInput" :placeholder="t('Type a message...')" @keyup.enter="sendChatMessage"></el-input>
      <el-button :icon="Position" type="primary" @click="sendChatMessage"></el-button>
    </div>
  </div>
</template>
<script setup>
import {Close, Position} from '@element-plus/icons-vue'
import {isChatOpen, chatMessages, currentUser, formatTime, chatInput, sendChatMessage, t} from '../store.js'
</script>
<style scoped>
.chat-drawer {
  position: fixed;
  top: var(--navbar-h);
  right: 0;
  width: 350px;
  height: calc(100vh - var(--navbar-h));
  background: var(--card-bg);
  border-left: 1px solid var(--border);
  box-shadow: var(--sh-lg);
  z-index: 150;
  display: flex;
  flex-direction: column;

  transform: translateX(100%);
  visibility: hidden;
  transition: transform 0.3s ease, visibility 0s 0.3s;
}

.chat-drawer.open {
  transform: translateX(0);
  visibility: visible;
  transition: transform 0.3s ease, visibility 0s;
}

.chat-header {
  padding: 15px;
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.chat-input-area {
  padding: 15px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 8px;
}

/* 移动端聊天室占满屏幕 */
@media (max-width: 768px) {
  .chat-drawer {
    width: 100%;
  }
}
</style>