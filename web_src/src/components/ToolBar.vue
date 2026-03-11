<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="toolbar">
    <el-input class="search-input" v-model="searchQuery" :placeholder="t('Search source, translation, comment...')"
              :prefix-icon="Search" clearable @input="handleSearch"></el-input>
    <div class="filter-group">
      <button v-for="f in filterTabs" :key="f.key" :class="['filter-btn', { active: statusFilter === f.key }]"
              @click="setFilter(f.key)">
        {{ t(f.label) }} <span class="filter-count">{{ f.count }}</span>
      </button>
    </div>
  </div>
</template>
<script setup>
import {Search} from '@element-plus/icons-vue'
import {searchQuery, handleSearch, filterTabs, statusFilter, setFilter, t} from '../store.js'
</script>
<style scoped>
.toolbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--card-bg);
  border-bottom: 1px solid var(--border);
  padding: 8px 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.toolbar .search-input {
  max-width: 320px;
  min-width: 180px;
}

.filter-group {
  display: flex;
  background: var(--bg-main);
  border-radius: 7px;
  padding: 3px;
  border: 1px solid var(--border);
  gap: 2px;
  overflow-x: auto;
  scrollbar-width: none;
}

.filter-group::-webkit-scrollbar {
  display: none;
}

.filter-btn {
  background: transparent;
  border: none;
  color: var(--text-sec);
  padding: 5px 11px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 5px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 5px;
  transition: all .18s;
}

.filter-btn:hover {
  background: rgba(0, 0, 0, .04);
  color: var(--text-main);
}

html.dark .filter-btn:hover {
  background: rgba(255, 255, 255, .06);
}

.filter-btn.active {
  background: var(--card-bg);
  color: #409EFF;
  box-shadow: var(--sh-sm);
  font-weight: 600;
}

.filter-count {
  font-size: 10px;
  background: var(--border);
  color: var(--text-muted);
  padding: 0 5px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
  line-height: 16px;
}

.filter-btn.active .filter-count {
  background: rgba(64, 158, 255, .15);
  color: #409EFF;
}

/* 移动端搜索独占一行，按钮横向平滑滚动 */
@media (max-width: 768px) {
  .toolbar {
    padding: 10px 10px;
    gap: 8px;
  }

  .toolbar .search-input {
    max-width: 100%;
    width: 100%;
    margin-bottom: 2px;
  }

  .filter-group {
    width: 100%;
    padding-bottom: 2px;
    -webkit-overflow-scrolling: touch;
  }
}
</style>