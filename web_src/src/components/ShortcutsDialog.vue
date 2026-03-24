<!--
Copyright (c) 2025-2026, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <el-dialog v-model="isShortcutsOpen" :title="t('Keyboard Shortcuts')" width="500px" align-center>
    <div class="shortcuts-container">
      <div class="shortcut-row" v-for="(sc, i) in shortcuts" :key="i">
        <div class="sc-desc">{{ sc.desc }}</div>
        <div class="sc-keys">
          <kbd v-for="(k, j) in sc.keys" :key="j">{{ k }}</kbd>
        </div>
      </div>
    </div>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="isShortcutsOpen = false">{{ t('Close') }}</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup>
import {computed} from 'vue'
import {isShortcutsOpen} from '../stores/ui.js'
import {t} from '../stores/auth.js'

const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
const ctrlKey = isMac ? 'Cmd' : 'Ctrl'

const shortcuts = computed(() => [
  {desc: t('Save & Next Untranslated'), keys: [ctrlKey, 'Enter']},
  {desc: t('Toggle Reviewed'), keys: [ctrlKey, 'R']},
  {desc: t('Toggle Fuzzy'), keys: [ctrlKey, 'F']},
  {desc: t('AI Translate Selected'), keys: [ctrlKey, 'T']},
  {desc: t('Copy Source Text'), keys: [ctrlKey, 'Shift', 'C']},
  {desc: t('Undo'), keys: [ctrlKey, 'Z']},
  {desc: t('Redo'), keys: [ctrlKey, 'Y']},
  {desc: t('Refresh Data'), keys: ['F5']},
])
</script>

<style scoped>
.shortcuts-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.shortcut-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--card-bg-alt);
  border-radius: 6px;
  border: 1px solid var(--border);
}

.sc-desc {
  font-size: 14px;
  color: var(--text-main);
}

.sc-keys {
  display: flex;
  gap: 4px;
}

kbd {
  background-color: var(--bg-main);
  border: 1px solid var(--border);
  border-bottom-width: 2px;
  border-radius: 4px;
  padding: 2px 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--text-main);
  min-width: 24px;
  text-align: center;
}

@media (max-width: 480px) {
  :deep(.el-dialog) {
    width: 92% !important;
  }

  .sc-desc {
    font-size: 13px;
  }
}
</style>