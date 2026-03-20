<!--
Copyright (c) 2025-2026, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <transition name="conflict-slide">
    <div class="conflict-panel" @click.stop>
      <div class="conflict-panel-header">
        <span class="conflict-panel-title">⚠️ {{ t('Conflict detected') }}</span>
        <span class="conflict-panel-sub">{{ row.conflictData.user }} {{ t('just updated this entry') }}</span>
      </div>
      <div class="conflict-cols">
        <div class="conflict-col">
          <div class="conflict-col-label conflict-col-label--mine">{{ t('Your version') }}</div>
          <div class="conflict-text" v-html="diff.htmlA"></div>
        </div>
        <div class="conflict-divider"></div>
        <div class="conflict-col">
          <div class="conflict-col-label conflict-col-label--server">{{ t('Server version') }}</div>
          <div class="conflict-text" v-html="diff.htmlB"></div>
        </div>
      </div>
      <div class="conflict-actions">
        <el-button size="small" @click="$emit('keep-mine')">{{ t('Keep mine') }}</el-button>
        <el-button size="small" type="primary" @click="$emit('use-server')">{{ t('Use latest') }}</el-button>
      </div>
    </div>
  </transition>
</template>

<script setup>
import {computed} from 'vue'
import {t} from '../../stores/auth.js'
import {computeDiff} from '../../composables/useDiff.js'

const props = defineProps({
  row: {type: Object, required: true}
})

defineEmits(['keep-mine', 'use-server'])

const diff = computed(() => {
  if (!props.row.conflictData) return {htmlA: '', htmlB: ''}
  const yourText = props.row.is_plural
      ? (props.row.plural_translations[props.row.conflictData.plural_index] ?? '')
      : (props.row.translation ?? '')
  return computeDiff(yourText, props.row.conflictData.serverText ?? '')
})
</script>

<style scoped>
.conflict-panel {
  margin-top: 8px;
  background: var(--card-bg-alt);
  border: 1.5px solid rgba(245, 158, 11, 0.45);
  border-radius: 10px;
  padding: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  z-index: 20;
}

.conflict-panel-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 10px;
}

.conflict-panel-title {
  font-size: 12px;
  font-weight: 700;
  color: #d97706;
}

.conflict-panel-sub {
  font-size: 11px;
  color: var(--text-muted);
}

.conflict-cols {
  display: flex;
  gap: 0;
  margin-bottom: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.conflict-col {
  flex: 1;
  min-width: 0;
  padding: 8px 10px;
}

.conflict-col:first-child {
  background: rgba(239, 68, 68, 0.04);
}

.conflict-col:last-child {
  background: rgba(34, 197, 94, 0.04);
}

.conflict-divider {
  width: 1px;
  background: var(--border);
  flex-shrink: 0;
}

.conflict-col-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 5px;
}

.conflict-col-label--mine {
  color: #ef4444;
}

.conflict-col-label--server {
  color: #22c55e;
}

.conflict-text {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-main);
  word-break: break-word;
  white-space: pre-wrap;
  font-family: 'Inter', sans-serif;
}

.conflict-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

:deep(.diff-removed) {
  background: rgba(239, 68, 68, 0.18);
  color: #dc2626;
  border-radius: 2px;
  padding: 0 2px;
  text-decoration: line-through;
  text-decoration-color: rgba(220, 38, 38, 0.6);
}

:deep(.diff-added) {
  background: rgba(34, 197, 94, 0.18);
  color: #16a34a;
  border-radius: 2px;
  padding: 0 2px;
}

html.dark :deep(.diff-removed) {
  background: rgba(239, 68, 68, 0.22);
  color: #f87171;
}

html.dark :deep(.diff-added) {
  background: rgba(34, 197, 94, 0.22);
  color: #4ade80;
}

.conflict-slide-enter-active {
  animation: conflict-drop 0.22s cubic-bezier(0.22, 1, 0.36, 1);
}

.conflict-slide-leave-active {
  animation: conflict-drop 0.18s cubic-bezier(0.22, 1, 0.36, 1) reverse;
}

@keyframes conflict-drop {
  from {
    opacity: 0;
    transform: translateY(-6px) scaleY(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scaleY(1);
  }
}

@media (max-width: 768px) {
  .conflict-cols {
    flex-direction: column;
  }

  .conflict-divider {
    width: 100%;
    height: 1px;
  }
}
</style>