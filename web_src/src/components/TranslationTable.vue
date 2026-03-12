<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="translation-card">
    <el-table
        :data="tableData"
        v-loading="loading"
        :row-class-name="tableRowClassName"
        row-key="id"
        style="width: 100%"
        :scrollbar-always-on="false"
    >
      <el-table-column :label="t('Original')" min-width="50%">
        <template #default="{ row }">
          <div class="src-wrap">
            <el-input
                type="textarea"
                autosize
                readonly
                v-model="row.source"
                class="source-input"
            ></el-input>
            <el-tag v-if="row.comment" size="small" type="info" effect="plain"
                    style="align-self:flex-start;max-width:100%;overflow:hidden;text-overflow:ellipsis">{{
                row.comment
              }}
            </el-tag>
          </div>
        </template>
      </el-table-column>

      <el-table-column :label="t('Translation')" min-width="50%">
        <template #default="{ row }">
          <div
              class="editor-cell"
              :class="{
                'has-others': othersEditing(row).length > 0,
                'is-self-editing': activeRowId === row.id,
                'has-conflict': !!row.conflictData,
                'is-ai-loading': row.isAiLoading,
              }"
              :ref="el => { if (el) cellRefs[row.id] = el }"
              :data-row-id="row.id"
              @mouseenter="onCellEnter(row)"
              @mouseleave="onCellLeave(row)"
          >
            <!-- ── AI Loading Mask ─────────────────────────────────── -->
            <div v-if="row.isAiLoading" class="ai-loading-mask">
              <div class="ai-scan-line"></div>
            </div>

            <!-- ── Conflict Warning Badge ─────────────────────────── -->
            <div
                v-if="row.conflictData"
                class="conflict-badge"
                @click.stop="toggleConflict(row)"
                :title="t('Conflict detected')"
            >
              <el-icon class="conflict-icon-blink"><WarningFilled /></el-icon>
            </div>

            <!-- ── Translation Inputs ─────────────────────────────── -->
            <div v-if="row.is_plural">
              <div v-for="(_, idx) in row.plural_translations" :key="idx" style="margin-bottom:10px">
                <div class="plural-label">{{ t('Form') }} {{ idx }}</div>
                <el-input
                    type="textarea"
                    autosize
                    v-model="row.plural_translations[idx]"
                    class="editor-input"
                    @focus="onEditorFocus(row)"
                    @blur="updateTranslation(row, idx)"
                    :disabled="currentUser.role === 'viewer' || row.isAiLoading"
                ></el-input>
              </div>
            </div>
            <el-input
                v-else
                type="textarea"
                autosize
                v-model="row.translation"
                class="editor-input"
                @focus="onEditorFocus(row)"
                @blur="updateTranslation(row)"
                :disabled="currentUser.role === 'viewer' || row.isAiLoading"
            ></el-input>

            <!-- ── Conflict Resolution Panel ──────────────────────── -->
            <transition name="conflict-slide">
              <div
                  v-if="row.conflictData && conflictOpenMap[row.id]"
                  class="conflict-panel"
                  @click.stop
              >
                <div class="conflict-panel-header">
                  <span class="conflict-panel-title">⚠️ {{ t('Conflict detected') }}</span>
                  <span class="conflict-panel-sub">{{ row.conflictData.user }} {{ t('just updated this entry') }}</span>
                </div>
                <div class="conflict-cols">
                  <div class="conflict-col">
                    <div class="conflict-col-label conflict-col-label--mine">{{ t('Your version') }}</div>
                    <div class="conflict-text" v-html="getConflictDiff(row).htmlA"></div>
                  </div>
                  <div class="conflict-divider"></div>
                  <div class="conflict-col">
                    <div class="conflict-col-label conflict-col-label--server">{{ t('Server version') }}</div>
                    <div class="conflict-text" v-html="getConflictDiff(row).htmlB"></div>
                  </div>
                </div>
                <div class="conflict-actions">
                  <el-button size="small" @click="keepMine(row)">{{ t('Keep mine') }}</el-button>
                  <el-button size="small" type="primary" @click="useServer(row)">{{ t('Use latest') }}</el-button>
                </div>
              </div>
            </transition>
          </div>
        </template>
      </el-table-column>

      <el-table-column :label="t('Status')" width="140" align="center" class-name="status-column">
        <template #default="{ row }">
          <div class="status-actions">
            <el-tooltip :content="t('AI Translate')" placement="top" v-if="currentUser.role !== 'viewer'">
              <el-button type="primary" plain :icon="MagicStick" circle size="small"
                         @click="requestAITranslation(row)"
                         :loading="row.isAiLoading"></el-button>
            </el-tooltip>

            <el-tooltip :content="t('Reviewed')" placement="top"
                        v-if="['admin', 'reviewer'].includes(currentUser.role)">
              <el-button :type="row.is_reviewed ? 'success' : 'info'" :icon="CircleCheckFilled" circle size="small"
                         @click="toggleStatus(row, 'reviewed')"></el-button>
            </el-tooltip>
            <el-button v-else-if="row.is_reviewed" type="success" :icon="CircleCheckFilled" circle size="small"
                       disabled></el-button>

            <el-tooltip :content="t('Fuzzy')" placement="top" v-if="currentUser.role !== 'viewer'">
              <el-button :type="row.is_fuzzy ? 'warning' : 'info'" :icon="WarningFilled" circle size="small"
                         @click="toggleStatus(row, 'fuzzy')"></el-button>
            </el-tooltip>
            <el-button v-else-if="row.is_fuzzy" type="warning" :icon="WarningFilled" circle size="small"
                       disabled></el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="empty-state" v-if="!loading && tableData.length === 0">
      <svg viewBox="0 0 24 24">
        <path
            d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 11c-.55 0-1-.45-1-1V8c0-.55.45-1 1-1s1 .45 1 1v4c0 .55-.45 1-1 1zm1 4h-2v-2h2v2z"/>
      </svg>
      <p>{{ t(searchQuery || statusFilter !== 'all' ? 'No matching entries' : 'No entries available') }}</p>
    </div>

    <!-- ── Editors Overlay (existing) ─────────────────────────────── -->
    <Teleport to="body">
      <transition name="overlay-fade">
        <div
            v-if="overlayVisible"
            class="editors-overlay-fixed"
            :style="overlayStyle"
        >
          <div v-for="name in overlayEditors" :key="name" class="editor-chip">
            <div class="editor-avatar" :style="{ background: avatarColor(name) }">
              {{ (name || '?')[0].toUpperCase() }}
            </div>
            <span class="editor-name">{{ name }}</span>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- ── AI Chip Overlay ────────────────────────────────────────── -->
    <Teleport to="body">
      <transition name="overlay-fade">
        <div
            v-if="aiChipVisible"
            class="ai-chip-fixed"
            :style="aiChipStyle"
        >
          <span class="ai-chip-sparkle">✨</span>
          <span class="ai-chip-label">AI</span>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<script setup>
import {ref, reactive, computed, watch, nextTick, onBeforeUnmount} from 'vue'
import {MagicStick, CircleCheckFilled, WarningFilled} from '@element-plus/icons-vue'
import {
  tableData, loading, tableRowClassName, hlPh, currentUser,
  onEditorFocus, updateTranslation, requestAITranslation, toggleStatus,
  searchQuery, statusFilter, t, avatarColor, activeRowId
} from '../store.js'

// ── Cell ref map: rowId → DOM element ──────────────────────────────────────
const cellRefs = reactive({})

// ── Editors Overlay (existing logic) ───────────────────────────────────────
const hoveredRowId = ref(null)
const overlayStyle = ref({top: '0px', left: '0px'})

const othersEditing = (row) =>
    (row.active_editors || []).filter(name => name !== currentUser.name)

const overlayRow = computed(() => {
  if (activeRowId.value !== null) {
    const row = tableData.value.find(r => r.id === activeRowId.value)
    if (row && othersEditing(row).length > 0) return row
  }
  if (hoveredRowId.value !== null) {
    const row = tableData.value.find(r => r.id === hoveredRowId.value)
    if (row && othersEditing(row).length > 0) return row
  }
  return null
})

const overlayEditors = computed(() => overlayRow.value ? othersEditing(overlayRow.value) : [])
const overlayVisible = computed(() => overlayEditors.value.length > 0)

const updateOverlayPosition = (rowId) => {
  const el = cellRefs[rowId]
  if (!el) return
  const rect = el.getBoundingClientRect()
  overlayStyle.value = {top: `${rect.top}px`, left: `${rect.left}px`}
}

const onCellEnter = (row) => {
  hoveredRowId.value = row.id
  if (othersEditing(row).length > 0) updateOverlayPosition(row.id)
}

const onCellLeave = (row) => {
  if (activeRowId.value !== row.id) hoveredRowId.value = null
}

// ── AI Chip Overlay ─────────────────────────────────────────────────────────
const aiChipStyle = ref({top: '0px', left: '0px'})
const aiLoadingRow = computed(() => tableData.value.find(r => r.isAiLoading))
const aiChipVisible = computed(() => !!aiLoadingRow.value)

const updateAiChipPosition = () => {
  if (!aiLoadingRow.value) return
  const el = cellRefs[aiLoadingRow.value.id]
  if (!el) return
  const rect = el.getBoundingClientRect()
  aiChipStyle.value = {top: `${rect.top}px`, left: `${rect.left}px`}
}

watch(aiChipVisible, (visible) => {
  if (visible) nextTick(updateAiChipPosition)
})

// ── Conflict Resolution ─────────────────────────────────────────────────────
const conflictOpenMap = reactive({})

const toggleConflict = (row) => {
  conflictOpenMap[row.id] = !conflictOpenMap[row.id]
}

const keepMine = (row) => {
  conflictOpenMap[row.id] = false
  row.conflictData = null
  updateTranslation(row)
}

const useServer = (row) => {
  if (!row.conflictData) return
  const pIdx = row.conflictData.plural_index ?? 0
  if (row.is_plural) {
    row.plural_translations[pIdx] = row.conflictData.serverText
  } else {
    row.translation = row.conflictData.serverText
  }
  conflictOpenMap[row.id] = false
  row.conflictData = null
}

const computeDiff = (textA, textB) => {
  const escape = (s) =>
      String(s)
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/\n/g, '<br>')

  if (textA === textB) {
    const e = escape(textA)
    return {htmlA: e, htmlB: e}
  }
  
  const tokenize = (s) => s.match(/\S+|\s+/g) || []
  const tokA = tokenize(textA)
  const tokB = tokenize(textB)
  
  if (tokA.length * tokB.length > 12000) {
    return {
      htmlA: `<mark class="diff-removed">${escape(textA)}</mark>`,
      htmlB: `<mark class="diff-added">${escape(textB)}</mark>`,
    }
  }
  
  const n = tokA.length, m = tokB.length
  const dp = Array.from({length: n + 1}, () => new Uint16Array(m + 1))
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      dp[i][j] = tokA[i - 1] === tokB[j - 1]
          ? dp[i - 1][j - 1] + 1
          : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }

  // Traceback
  const opsA = [], opsB = []
  let i = n, j = m
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && tokA[i - 1] === tokB[j - 1]) {
      opsA.unshift({tok: tokA[i - 1], type: 'same'})
      opsB.unshift({tok: tokB[j - 1], type: 'same'})
      i--; j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      opsB.unshift({tok: tokB[j - 1], type: 'added'})
      j--
    } else {
      opsA.unshift({tok: tokA[i - 1], type: 'removed'})
      i--
    }
  }

  const render = (ops) => ops.map(op => {
    const e = escape(op.tok)
    if (op.type === 'same') return e
    if (op.type === 'removed') return `<mark class="diff-removed">${e}</mark>`
    return `<mark class="diff-added">${e}</mark>`
  }).join('')

  return {htmlA: render(opsA), htmlB: render(opsB)}
}

const getConflictDiff = (row) => {
  if (!row.conflictData) return {htmlA: '', htmlB: ''}
  const yourText = row.is_plural
      ? (row.plural_translations[row.conflictData.plural_index] ?? '')
      : (row.translation ?? '')
  return computeDiff(yourText, row.conflictData.serverText ?? '')
}

// ── Shared scroll/resize handler ────────────────────────────────────────────
const handleScroll = () => {
  const rowId = activeRowId.value ?? hoveredRowId.value
  if (rowId != null && overlayVisible.value) updateOverlayPosition(rowId)
  updateAiChipPosition()
}

window.addEventListener('scroll', handleScroll, {passive: true})
window.addEventListener('resize', handleScroll, {passive: true})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', handleScroll)
  window.removeEventListener('resize', handleScroll)
})
</script>

<style scoped>
.translation-card {
  overflow: visible;
}

:deep(.el-table) {
  overflow: visible !important;
}

:deep(.el-table__inner-wrapper) {
  overflow: visible !important;
}

:deep(.el-table__body-wrapper) {
  overflow: visible !important;
}

/* Status border */
:deep(.el-table .el-table__row.row-reviewed > td:first-child) {
  border-left: 3px solid var(--st-reviewed) !important;
}

:deep(.el-table .el-table__row.row-translated > td:first-child) {
  border-left: 3px solid var(--st-translated) !important;
}

:deep(.el-table .el-table__row.row-fuzzy > td:first-child) {
  border-left: 3px solid var(--st-fuzzy) !important;
}

:deep(.el-table .el-table__row.row-untranslated > td:first-child) {
  border-left: 3px solid var(--st-untranslated) !important;
}

/* Source text */
.src-wrap {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

:deep(.source-input .el-textarea__inner) {
  font-family: 'Inter', sans-serif !important;
  font-size: 13.5px !important;
  line-height: 1.65 !important;
  background: transparent !important;
  border: 1px solid transparent !important;
  padding: 6px 8px;
  color: var(--text-main) !important;
  resize: none;
  box-shadow: none !important;
  cursor: text;
  overflow: hidden !important;
  word-break: break-word;
}

:deep(.source-input .el-textarea__inner:focus) {
  box-shadow: none !important;
  border-color: transparent !important;
  background: transparent !important;
}

:deep(.hl-ph) {
  color: var(--hl-txt);
  font-family: 'JetBrains Mono', monospace;
  font-size: 11.5px;
  background: var(--hl-bg);
  padding: 1px 5px;
  border-radius: 4px;
}

/* Editor cell */
.editor-cell {
  position: relative;
}

/* Yellow border when others are editing */
.editor-cell.has-others :deep(.editor-input .el-textarea__inner) {
  border-color: var(--st-fuzzy) !important;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15) !important;
}

/* Orange border when conflict */
.editor-cell.has-conflict :deep(.editor-input .el-textarea__inner) {
  border-color: #f59e0b !important;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2) !important;
}

/* Textarea */
:deep(.editor-input .el-textarea__inner) {
  font-family: 'Inter', sans-serif !important;
  font-size: 13.5px !important;
  line-height: 1.65 !important;
  background: transparent !important;
  border: 1px solid transparent !important;
  border-radius: 6px;
  padding: 6px 8px;
  color: var(--text-main) !important;
  resize: none;
  box-shadow: none !important;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
  overflow: hidden !important;
  word-break: break-word;
}

:deep(.editor-input:hover .el-textarea__inner) {
  background: var(--card-bg-alt) !important;
  border-color: var(--border) !important;
}

:deep(.editor-input .el-textarea__inner:focus) {
  background: var(--card-bg) !important;
  border-color: #409EFF !important;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.12) !important;
}

.plural-label {
  font-size: 11px;
  font-weight: 600;
  color: #409EFF;
  margin-bottom: 3px;
}

.status-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.empty-state {
  padding: 64px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--text-muted);
}

.empty-state svg {
  width: 48px;
  height: 48px;
  fill: var(--border);
}

/* ── AI Loading Mask ────────────────────────────────────────────────────── */
.ai-loading-mask {
  position: absolute;
  inset: 0;
  background: rgba(124, 58, 237, 0.07);
  border: 1.5px solid rgba(124, 58, 237, 0.28);
  border-radius: 6px;
  z-index: 10;
  pointer-events: all; /* block interaction */
  overflow: hidden;
  cursor: not-allowed;
}

.ai-scan-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 55%;
  background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(124, 58, 237, 0.22) 40%,
      rgba(167, 139, 250, 0.32) 50%,
      rgba(124, 58, 237, 0.22) 60%,
      transparent 100%
  );
  animation: ai-scan 1.6s ease-in-out infinite;
}

@keyframes ai-scan {
  0% {
    transform: translateX(-120%);
  }
  100% {
    transform: translateX(280%);
  }
}

html.dark .ai-loading-mask {
  background: rgba(167, 139, 250, 0.1);
  border-color: rgba(167, 139, 250, 0.35);
}

/* ── Conflict Badge ──────────────────────────────────────────────────────── */
.conflict-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 15;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(245, 158, 11, 0.15);
  border: 1px solid rgba(245, 158, 11, 0.4);
  transition: background 0.2s;
}

.conflict-badge:hover {
  background: rgba(245, 158, 11, 0.28);
}

.conflict-icon-blink {
  color: #f59e0b;
  font-size: 13px;
  animation: conflict-blink 1.2s ease-in-out infinite;
}

@keyframes conflict-blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

/* ── Conflict Resolution Panel ──────────────────────────────────────────── */
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

/* Diff highlight marks */
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

/* Panel animation */
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

/* ════════════════════════════════════════════════════
   移动端卡片化布局重写 (Table-to-Card)
════════════════════════════════════════════════════ */
@media (max-width: 768px) {
  :deep(.source-input) {
    pointer-events: none;
  }

  :deep(.editor-input .el-textarea__inner:not(:focus)) {
    touch-action: pan-y;
  }

  .translation-card {
    background: transparent;
    border: none;
    box-shadow: none;
    margin-bottom: 0;
  }

  :deep(.el-table), :deep(.el-table__inner-wrapper), :deep(.el-table__body-wrapper),
  :deep(.el-table__body), :deep(tbody), :deep(tr), :deep(td) {
    display: block !important;
    width: 100% !important;
  }

  :deep(.el-table__header-wrapper) {
    display: none !important;
  }

  :deep(.el-table__row) {
    margin-bottom: 16px;
    background: var(--card-bg) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  }

  :deep(.el-table .el-table__cell) {
    padding: 12px !important;
    border-bottom: none !important;
  }

  :deep(.el-table .el-table__cell:nth-child(1)) {
    border-bottom: 1px dashed var(--border) !important;
    padding-bottom: 16px !important;
  }

  :deep(.el-table .el-table__cell:nth-child(3)) {
    position: absolute;
    top: 10px;
    right: 10px;
    width: auto !important;
    padding: 0 !important;
    background: transparent !important;
    z-index: 10;
  }

  .status-actions {
    background: var(--card-bg-alt);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 2px 4px;
    box-shadow: var(--sh-sm);
  }

  .status-actions :deep(.el-button) {
    transform: scale(0.9);
    margin: 0 2px;
  }

  :deep(.el-table .el-table__row.row-reviewed) {
    border-left: 4px solid var(--st-reviewed) !important;
  }

  :deep(.el-table .el-table__row.row-translated) {
    border-left: 4px solid var(--st-translated) !important;
  }

  :deep(.el-table .el-table__row.row-fuzzy) {
    border-left: 4px solid var(--st-fuzzy) !important;
  }

  :deep(.el-table .el-table__row.row-untranslated) {
    border-left: 4px solid var(--st-untranslated) !important;
  }

  :deep(.el-table .el-table__row > td:first-child) {
    border-left: none !important;
  }

  .conflict-cols {
    flex-direction: column;
  }

  .conflict-divider {
    width: 100%;
    height: 1px;
  }
}
</style>

<style>
/* ── Editors Overlay (global, teleported) ────────────────────────────────── */
.editors-overlay-fixed {
  position: fixed;
  z-index: 9000;
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 20px;
  padding: 3px 8px 3px 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  pointer-events: none;
  white-space: nowrap;
  transform: translateY(calc(-100% - 4px));
}

.editors-overlay-fixed .editor-chip {
  display: flex;
  align-items: center;
  gap: 5px;
}

.editors-overlay-fixed .editor-chip + .editor-chip::before {
  content: '';
  display: inline-block;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--text-muted, #94a3b8);
  margin-right: 1px;
}

.editors-overlay-fixed .editor-avatar {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.editors-overlay-fixed .editor-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-sec, #64748b);
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── AI Chip (global, teleported) ────────────────────────────────────────── */
.ai-chip-fixed {
  position: fixed;
  z-index: 9001;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: rgba(124, 58, 237, 0.1);
  border: 1px solid rgba(124, 58, 237, 0.38);
  color: #7c3aed;
  border-radius: 20px;
  padding: 3px 10px 3px 7px;
  box-shadow: 0 4px 14px rgba(124, 58, 237, 0.18);
  pointer-events: none;
  white-space: nowrap;
  transform: translateY(calc(-100% - 4px));
  font-size: 12px;
  font-weight: 600;
}

html.dark .ai-chip-fixed {
  background: rgba(167, 139, 250, 0.14);
  border-color: rgba(167, 139, 250, 0.45);
  color: #a78bfa;
}

.ai-chip-sparkle {
  display: inline-block;
  animation: ai-sparkle 0.9s ease-in-out infinite alternate;
}

.ai-chip-label {
  letter-spacing: 0.03em;
}

@keyframes ai-sparkle {
  from {
    opacity: 0.55;
    transform: scale(0.88);
  }
  to {
    opacity: 1;
    transform: scale(1.14);
  }
}

/* ── Shared overlay animation ────────────────────────────────────────────── */
.overlay-fade-enter-active, .overlay-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.overlay-fade-enter-from, .overlay-fade-leave-to {
  opacity: 0;
  transform: translateY(calc(-100% - 1px));
}
</style>