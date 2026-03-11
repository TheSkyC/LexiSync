<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="toast-container">
    <div v-for="t in toasts" :key="t.id" :class="['toast', `t-${t.type}`, { 'toast-leaving': t.leaving }]">
      <svg class="toast-icon" viewBox="0 0 20 20">
        <path v-if="t.type==='success'"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"/>
        <path v-else-if="t.type==='error'"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"/>
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
import {toasts, toastDismiss} from '../store.js'
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
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 11px 14px;
  box-shadow: var(--sh-lg);
  pointer-events: auto;
  animation: toast-in .3s both;
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
}

.toast-close-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 16px;
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
</style>