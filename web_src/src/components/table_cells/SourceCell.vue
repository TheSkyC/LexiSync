<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="src-wrap">
    <el-input
        type="textarea"
        autosize
        readonly
        :model-value="source"
        class="source-input"
    ></el-input>
    <el-tag v-if="comment" size="small" type="info" effect="plain" class="comment-tag">
      {{ comment }}
    </el-tag>
  </div>
</template>

<script setup>
defineProps({
  source: String,
  comment: String,
})
</script>

<style scoped>
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

.comment-tag {
  align-self: flex-start;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 768px) {
  :deep(.source-input) {
    pointer-events: none;
  }
}
</style>