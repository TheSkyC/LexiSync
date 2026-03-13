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

    <el-tooltip
        v-if="comment"
        placement="top"
        :disabled="isExpanded"
        :show-after="300"
    >
      <template #content>
        <div class="tooltip-content">
          {{ comment }}
        </div>
      </template>

      <div
          class="comment-tag-wrap"
          :class="{ 'is-expandable': isLongComment, 'is-expanded': isExpanded }"
          @click="toggleExpand"
      >
        <div class="custom-comment-tag">
          {{ comment }}
        </div>
      </div>
    </el-tooltip>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  source: String,
  comment: String,
})

const isExpanded = ref(false)

const isLongComment = computed(() => {
  if (!props.comment) return false
  return props.comment.length > 60 || props.comment.includes('\n')
})

const toggleExpand = () => {
  if (isLongComment.value) {
    isExpanded.value = !isExpanded.value
  }
}
</script>

<style scoped>

.src-wrap {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 5px;
  width: 100%;
}

/* source textarea */

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
  overflow-wrap: anywhere;
}

/* Comment */

.comment-tag-wrap {
  justify-self: start;
  max-width: 100%;
  min-width: 0;
}

/* 关键修复 */
.custom-comment-tag {
  display: block; 
  max-width: 100%;
  padding: 2px 8px;
  font-size: 12px;
  color: var(--text-sec);
  background-color: var(--card-bg-alt);
  border: 1px solid var(--border);
  border-radius: 4px;
  transition: all 0.2s;
  box-sizing: border-box;
  text-align: left;
}

/* 未展开：单行截断 */

.comment-tag-wrap:not(.is-expanded) .custom-comment-tag {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 展开：自动换行 */

.comment-tag-wrap.is-expanded .custom-comment-tag {

  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

/* 可展开状态 */

.comment-tag-wrap.is-expandable .custom-comment-tag {
  cursor: pointer;
}

/* hover */

.comment-tag-wrap.is-expandable:hover .custom-comment-tag {
  border-color: #a0cfff;
  color: #409eff;
  background-color: rgba(64, 158, 255, 0.1);
}

html.dark .comment-tag-wrap.is-expandable:hover .custom-comment-tag {
  border-color: #337ecc;
  color: #79bbff;
  background-color: rgba(64, 158, 255, 0.15);
}

/* tooltip */

.tooltip-content {
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  max-width: 350px;
  line-height: 1.5;
}

/* mobile */

@media (max-width: 768px) {
  :deep(.source-input) {
    pointer-events: none;
  }
}

</style>