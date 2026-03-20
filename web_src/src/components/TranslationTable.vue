<!--
Copyright (c) 2025-2026, TheSkyC
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
          <SourceCell v-memo="[row.source, row.comment]" :source="row.source" :comment="row.comment"/>
        </template>
      </el-table-column>

      <el-table-column :label="t('Translation')" min-width="50%">
        <template #default="{ row }">
          <EditorCell :row="row"/>
        </template>
      </el-table-column>

      <el-table-column :label="t('Status')" width="140" align="center" class-name="status-column">
        <template #default="{ row }">
          <StatusCell :row="row"/>
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
  </div>
</template>

<script setup>
import {tableData, tableRowClassName, searchQuery, statusFilter} from '../stores/project.js'
import {loading} from '../stores/ui.js'
import {t} from '../stores/auth.js'
import SourceCell from './table_cells/SourceCell.vue'
import EditorCell from './table_cells/EditorCell.vue'
import StatusCell from './table_cells/StatusCell.vue'
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

  :deep(.el-table),
  :deep(.el-table__inner-wrapper),
  :deep(.el-table__body-wrapper) {
    display: block !important;
    width: 100% !important;
    overflow-x: hidden !important;
  }

  :deep(.el-table__body),
  :deep(tbody),
  :deep(tr),
  :deep(td) {
    display: block !important;
    width: 100% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
    overflow: hidden;
  }

  :deep(.el-table .el-table__cell) {
    padding: 12px !important;
    border-bottom: none !important;
    max-width: 100%;
  }

  :deep(.el-table__row) {
    margin-bottom: 16px;
    background: var(--card-bg) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    width: 100% !important;
    box-sizing: border-box !important;
    overflow: hidden;
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

  :deep(.el-table .cell) {
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
    padding: 0 !important;
    overflow: hidden !important;
  }
}
</style>