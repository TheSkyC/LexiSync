<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div
      class="editor-cell"
      :class="{
      'has-others': othersEditing.length > 0,
      'is-self-editing': activeRowId === row.id,
      'has-conflict': !!row.conflictData,
      'is-ai-loading': row.isAiLoading,
    }"
      :ref="cellRef"
      :data-row-id="row.id"
      @mouseenter="hoveredRowId = row.id"
      @mouseleave="hoveredRowId = null"
  >
    <!-- AI Loading Mask -->
    <div v-if="row.isAiLoading" class="ai-loading-mask">
      <div class="ai-scan-line"></div>
    </div>

    <!-- Conflict Warning Badge -->
    <div
        v-if="row.conflictData"
        class="conflict-badge"
        @click.stop="toggleConflict(row)"
        :title="t('Conflict detected')"
    >
      <el-icon class="conflict-icon-blink">
        <WarningFilled/>
      </el-icon>
    </div>

    <!-- Translation Inputs -->
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
            :disabled="!hasPermission('translate') || row.isAiLoading"
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
        :disabled="!hasPermission('translate') || row.isAiLoading"
    ></el-input>

    <!-- Conflict Resolution Panel -->
    <ConflictPanel
        v-if="row.conflictData && conflictOpenMap[row.id]"
        :row="row"
        @keep-mine="keepMine"
        @use-server="useServer"
    />

    <!-- Editors Overlay -->
    <Teleport to="body">
      <transition name="overlay-fade">
        <div v-if="overlayVisible" class="editors-overlay-fixed" :style="overlayStyle">
          <div v-for="name in othersEditing" :key="name" class="editor-chip">
            <div class="editor-avatar" :style="{ background: avatarColor(name) }">
              {{ (name || '?')[0].toUpperCase() }}
            </div>
            <span class="editor-name">{{ name }}</span>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- AI Chip Overlay -->
    <Teleport to="body">
      <transition name="overlay-fade">
        <div v-if="aiChipVisible" class="ai-chip-fixed" :style="overlayStyle">
          <span class="ai-chip-sparkle">✨</span>
          <span class="ai-chip-label">AI</span>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<script setup>
import {ref, reactive, computed} from 'vue'
import {WarningFilled} from '@element-plus/icons-vue'
import {
  currentUser, onEditorFocus, updateTranslation, t, avatarColor, activeRowId, hasPermission
} from '../../store.js'
import {useFloatingOverlay} from '../../composables/useFloatingOverlay.js'
import ConflictPanel from './ConflictPanel.vue'

const props = defineProps({
  row: {type: Object, required: true}
})

// --- State ---
const hoveredRowId = ref(null)
const conflictOpenMap = reactive({})

// --- Composables ---
const {
  cellRef,
  overlayStyle,
  overlayVisible: baseOverlayVisible,
  isTargetRow
} = useFloatingOverlay(props.row, hoveredRowId, activeRowId)

// --- Computed ---
const othersEditing = computed(() =>
    (props.row.active_editors || []).filter(name => name !== currentUser.name)
)
const overlayVisible = computed(() => baseOverlayVisible.value && othersEditing.value.length > 0)
const aiChipVisible = computed(() => isTargetRow.value && props.row.isAiLoading)

// --- Methods ---
const toggleConflict = () => {
  conflictOpenMap[props.row.id] = !conflictOpenMap[props.row.id]
}

const keepMine = () => {
  conflictOpenMap[props.row.id] = false
  props.row.conflictData = null
  updateTranslation(props.row)
}

const useServer = () => {
  if (!props.row.conflictData) return
  const pIdx = props.row.conflictData.plural_index ?? 0
  if (props.row.is_plural) {
    props.row.plural_translations[pIdx] = props.row.conflictData.serverText
  } else {
    props.row.translation = props.row.conflictData.serverText
  }
  conflictOpenMap[props.row.id] = false
  props.row.conflictData = null
}
</script>

<style scoped>
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

/* AI Loading Mask */
.ai-loading-mask {
  position: absolute;
  inset: 0;
  background: rgba(124, 58, 237, 0.07);
  border: 1.5px solid rgba(124, 58, 237, 0.28);
  border-radius: 6px;
  z-index: 10;
  pointer-events: all;
  overflow: hidden;
  cursor: not-allowed;
}

.ai-scan-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 55%;
  background: linear-gradient(90deg, transparent 0%, rgba(124, 58, 237, 0.22) 40%, rgba(167, 139, 250, 0.32) 50%, rgba(124, 58, 237, 0.22) 60%, transparent 100%);
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

/* Conflict Badge */
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
</style>