<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <Teleport to="body">
    <transition name="fade">
      <div v-if="isHistoryOpen" class="history-mask" @click="isHistoryOpen = false"></div>
    </transition>
    <div :class="['history-drawer', { open: isHistoryOpen }]">
      <div class="history-header">
        <div class="header-title">
          <el-icon><Clock /></el-icon>
          <span>{{ t('Audit Log') }}</span>
        </div>
        <div class="header-actions">
          <el-button :icon="Refresh" link @click="fetchAuditHistory" :loading="isHistoryLoading" :title="t('Refresh')"></el-button>
          <el-button :icon="Close" link @click="isHistoryOpen = false"></el-button>
        </div>
      </div>

      <div class="history-content" v-loading="isHistoryLoading">
        <div v-if="auditHistory.undo.length === 0 && auditHistory.redo.length === 0" class="empty-state">
          <p>{{ t('No history available') }}</p>
        </div>
        
        <el-timeline v-else style="padding: 15px;">
          <!-- Redo History (Future states) -->
          <el-timeline-item
            v-for="(item, index) in auditHistory.redo"
            :key="'redo-'+index"
            type="info"
            color="#e2e8f0"
            :timestamp="item.timestamp"
            placement="top"
            class="redo-item"
          >
            <el-card shadow="hover" class="history-card">
              <div class="history-desc">{{ item.description }}</div>
              <div class="history-user">
                <el-icon><User /></el-icon> {{ item.user }}
              </div>
            </el-card>
          </el-timeline-item>

          <!-- Current State Indicator -->
          <el-timeline-item
            v-if="auditHistory.undo.length > 0 || auditHistory.redo.length > 0"
            type="primary"
            color="#409EFF"
            size="large"
            :timestamp="t('Current State')"
            placement="top"
          >
          </el-timeline-item>

          <!-- Undo History (Past states) -->
          <el-timeline-item
            v-for="(item, index) in auditHistory.undo"
            :key="'undo-'+index"
            type="success"
            color="#22c55e"
            :timestamp="item.timestamp"
            placement="top"
          >
            <el-card shadow="hover" class="history-card">
              <div class="history-desc">{{ item.description }}</div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </div>
      
      <div class="history-footer" v-if="hasPermission('translate')">
         <el-button @click="triggerUndo" :disabled="auditHistory.undo.length === 0" :icon="RefreshLeft">{{ t('Undo') }}</el-button>
         <el-button @click="triggerRedo" :disabled="auditHistory.redo.length === 0" :icon="RefreshRight">{{ t('Redo') }}</el-button>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import {Close, Clock, Refresh, RefreshLeft, RefreshRight, User} from '@element-plus/icons-vue'
import {t, hasPermission} from '../stores/auth.js'
import {isHistoryOpen} from '../stores/ui.js'
import {auditHistory, isHistoryLoading, fetchAuditHistory, triggerUndo, triggerRedo} from '../stores/project.js'
</script>

<style scoped>
.history-mask {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.3);
  z-index: 1900;
}

.history-drawer {
  position: fixed;
  top: 0;
  bottom: 0;
  right: 0;
  width: 380px;
  background: var(--card-bg);
  border-left: 1px solid var(--border);
  box-shadow: -5px 0 20px rgba(0,0,0,0.1);
  z-index: 2000;
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.3s cubic-bezier(0.7, 0.3, 0.1, 1);
  visibility: hidden;
}

.history-drawer.open {
  transform: translateX(0);
  visibility: visible;
}

.history-header {
  padding: 15px 20px;
  height: var(--navbar-h);
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--text-main);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.history-content {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-main);
}

.history-card {
  --el-card-padding: 10px;
  border-radius: 6px;
  background: var(--card-bg);
  border: 1px solid var(--border);
}

.history-desc {
  font-size: 13px;
  color: var(--text-main);
  word-break: break-word;
}

.history-user {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.redo-item {
  opacity: 0.6;
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

.history-footer {
  padding: 15px;
  border-top: 1px solid var(--border);
  background: var(--card-bg);
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.history-footer .el-button {
  flex: 1;
}

@media (max-width: 768px) {
  .history-drawer {
    width: 85%;
    max-width: 100%;
  }
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>