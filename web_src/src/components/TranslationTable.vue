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
              'is-self-editing': activeRowId === row.id
            }"
              :ref="el => { if (el) cellRefs[row.id] = el }"
              @mouseenter="onCellEnter(row)"
              @mouseleave="onCellLeave(row)"
          >
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
                    :disabled="currentUser.role === 'viewer'"
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
                :disabled="currentUser.role === 'viewer'"
            ></el-input>
          </div>
        </template>
      </el-table-column>

      <el-table-column :label="t('Status')" width="140" align="center" class-name="status-column">
        <template #default="{ row }">
          <div class="status-actions">
            <el-tooltip :content="t('AI Translate')" placement="top" v-if="currentUser.role !== 'viewer'">
              <el-button type="primary" plain :icon="MagicStick" circle size="small"
                         @click="requestAITranslation(row)"></el-button>
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
  </div>
</template>

<script setup>
import {ref, reactive, computed, onBeforeUnmount} from 'vue'
import {MagicStick, CircleCheckFilled, WarningFilled} from '@element-plus/icons-vue'
import {
  tableData, loading, tableRowClassName, hlPh, currentUser,
  onEditorFocus, updateTranslation, requestAITranslation, toggleStatus,
  searchQuery, statusFilter, t, avatarColor, activeRowId
} from '../store.js'

// ── Cell ref map: rowId → DOM element ──────────────────────────────────────
const cellRefs = reactive({})

// ── Overlay state ───────────────────────────────────────────────────────────
const hoveredRowId = ref(null)
const overlayStyle = ref({top: '0px', left: '0px'})

const othersEditing = (row) =>
    (row.active_editors || []).filter(name => name !== currentUser.name)

// Which row should the overlay track?
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
  overlayStyle.value = {
    top: `${rect.top}px`,
    left: `${rect.left}px`,
  }
}

const onCellEnter = (row) => {
  hoveredRowId.value = row.id
  if (othersEditing(row).length > 0) updateOverlayPosition(row.id)
}

const onCellLeave = (row) => {
  if (activeRowId.value !== row.id) hoveredRowId.value = null
}

const handleScroll = () => {
  const rowId = activeRowId.value ?? hoveredRowId.value
  if (rowId != null && overlayVisible.value) updateOverlayPosition(rowId)
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

:deep(.source-input .el-textarea__inner),
:deep(.editor-input .el-textarea__inner) {
  overflow-y: auto !important;
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

/* ════════════════════════════════════════════════════
   移动端卡片化布局重写 (Table-to-Card)
════════════════════════════════════════════════════ */
@media (max-width: 768px) {
  .translation-card {
    background: transparent;
    border: none;
    box-shadow: none;
    margin-bottom: 0;
  }

  /* 拆解表格布局 */
  :deep(.el-table), :deep(.el-table__inner-wrapper), :deep(.el-table__body-wrapper),
  :deep(.el-table__body), :deep(tbody), :deep(tr), :deep(td) {
    display: block !important;
    width: 100% !important;
  }

  /* 隐藏表头 */
  :deep(.el-table__header-wrapper) {
    display: none !important;
  }

  /* 行转为独立卡片 */
  :deep(.el-table__row) {
    margin-bottom: 16px;
    background: var(--card-bg) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  }

  /* 单元格占满宽度 */
  :deep(.el-table .el-table__cell) {
    padding: 12px !important;
    border-bottom: none !important;
  }

  /* 原文单元格加虚线分隔 */
  :deep(.el-table .el-table__cell:nth-child(1)) {
    border-bottom: 1px dashed var(--border) !important;
    padding-bottom: 16px !important;
  }

  /* 状态操作组（第三列）脱离文档流，悬浮右上角 */
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

  /* 状态边色转移到整行容器 */
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

  /* 抹除原子单元格的左边框 */
  :deep(.el-table .el-table__row > td:first-child) {
    border-left: none !important;
  }
}
</style>

<style>
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

.overlay-fade-enter-active, .overlay-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.overlay-fade-enter-from, .overlay-fade-leave-to {
  opacity: 0;
  transform: translateY(calc(-100% - 1px));
}
</style>