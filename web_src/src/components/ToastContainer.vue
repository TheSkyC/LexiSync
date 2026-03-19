<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="toast-container" :class="shiftClass">
    <div v-for="t in toasts" :key="t.id" :class="['toast', `t-${t.type}`, { 'toast-leaving': t.leaving }]">
      <svg class="toast-icon" viewBox="0 0 20 20">
        <path v-if="t.type==='success'"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"/>
        <path v-else-if="t.type==='error'"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414-1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"/>
        <path v-else-if="t.type==='warning'"
              d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"/>
        <path v-else
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"/>
      </svg>
      <div class="toast-body">{{ t.message }}</div>
      <button class="toast-close-btn" @click="toastDismiss(t.id)">×</button>
    </div>
  </div>
</template>

<script setup>
import {computed} from 'vue'
import {toasts, toastDismiss, isHistoryOpen, isNavMenuOpen} from '../stores/ui.js'
import {isChatOpen, isUsersOpen} from '../stores/realtime.js'

const isRealDrawerOpen = computed(() =>
    isChatOpen.value || isUsersOpen.value || isHistoryOpen.value
)

const shiftClass = computed(() => {
  if (isRealDrawerOpen.value) return 'is-shifted-drawer'
  if (isNavMenuOpen.value) return 'is-shifted-menu'
  return ''
})
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 70px;
  right: 18px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
  max-width: 360px;
  transition: right 0.3s cubic-bezier(0.7, 0.3, 0.1, 1);
}

/* 侧边抽屉打开时 */
.toast-container.is-shifted-drawer {
  right: 410px;
}

/* 导航下拉菜单打开时 */
.toast-container.is-shifted-menu {
  right: 190px;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  /* 不支持毛玻璃的浏览器使用纯色 */
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 11px 14px;
  box-shadow: var(--sh-lg);
  pointer-events: auto;
  animation: toast-in .3s both;
}

@supports (backdrop-filter: blur(10px)) {
  .toast {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
  }

  html.dark .toast {
    background: rgba(22, 25, 32, 0.85);
  }
}

.toast.toast-leaving {
  animation: toast-out .25s forwards;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(24px) scale(.95);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@keyframes toast-out {
  to {
    opacity: 0;
    transform: translateX(24px) scale(.93);
  }
}

.toast-icon {
  width: 16px;
  height: 16px;
  margin-top: 1px;
  fill: currentColor;
}

.toast-body {
  flex: 1;
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.4;
}

.toast-close-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 16px;
  padding: 0 4px;
  margin-top: -2px;
}

.toast.t-success {
  border-left: 3px solid var(--st-reviewed);
  color: var(--st-reviewed);
}

.toast.t-error {
  border-left: 3px solid var(--st-untranslated);
  color: var(--st-untranslated);
}

.toast.t-warning {
  border-left: 3px solid var(--st-fuzzy);
  color: var(--st-fuzzy);
}

.toast.t-info {
  border-left: 3px solid var(--st-translated);
  color: var(--st-translated);
}

/* ── 移动端适配 ── */
@media (max-width: 768px) {
  .toast-container {
    right: 50% !important;
    transform: translateX(50%);
    top: auto;
    bottom: 80px;
    width: 90vw;
    max-width: 400px;
    align-items: center;
    transition: none;
  }

  .toast-container.is-shifted-drawer,
  .toast-container.is-shifted-menu {
    right: 50% !important;
  }

  @keyframes toast-in {
    from {
      opacity: 0;
      transform: translateY(12px) scale(.95);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }

  @keyframes toast-out {
    to {
      opacity: 0;
      transform: translateY(8px) scale(.93);
    }
  }
}
</style>