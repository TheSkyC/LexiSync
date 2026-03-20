<!--
Copyright (c) 2025-2026, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="status-actions">
    <!-- AI Translate: requires ai_translate permission -->
    <el-tooltip :content="t('AI Translate')" placement="top" v-if="hasPermission('ai_translate')">
      <el-button type="primary" plain :icon="MagicStick" circle size="small"
                 @click="handleAIRequest"
                 :loading="row.isAiLoading"></el-button>
    </el-tooltip>

    <!-- Reviewed: interactive button for users with review permission -->
    <el-tooltip :content="t('Reviewed')" placement="top" v-if="hasPermission('review')">
      <el-button :type="row.is_reviewed ? 'success' : 'info'" :icon="CircleCheckFilled" circle size="small"
                 @click="handleStatusToggle('reviewed', $event)"></el-button>
    </el-tooltip>
    <!-- Reviewed: read-only indicator for users without review permission -->
    <el-button v-else-if="row.is_reviewed" type="success" :icon="CircleCheckFilled" circle size="small"
               disabled></el-button>

    <!-- Fuzzy: interactive button for users with fuzzy permission -->
    <el-tooltip :content="t('Fuzzy')" placement="top" v-if="hasPermission('fuzzy')">
      <el-button :type="row.is_fuzzy ? 'warning' : 'info'" :icon="WarningFilled" circle size="small"
                 @click="handleStatusToggle('fuzzy', $event)"></el-button>
    </el-tooltip>
    <!-- Fuzzy: read-only indicator for users without fuzzy permission -->
    <el-button v-else-if="row.is_fuzzy" type="warning" :icon="WarningFilled" circle size="small"
               disabled></el-button>
  </div>
</template>

<script setup>
import {MagicStick, CircleCheckFilled, WarningFilled} from '@element-plus/icons-vue'
import {requestAITranslation, toggleStatus} from '../../stores/project.js'
import {t, hasPermission} from '../../stores/auth.js'

const props = defineProps({
  row: {type: Object, required: true}
})

const handleAIRequest = (event) => {
  requestAITranslation(props.row);
  event.currentTarget?.blur();
}

const handleStatusToggle = (type, event) => {
  toggleStatus(props.row, type);
  event.currentTarget?.blur();
}
</script>

<style scoped>
.status-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
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
}
</style>