<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <ToastContainer/>
  <AuthDialog/>
  <ShortcutsDialog/>

  <div class="app-wrap" v-if="!showAuthDialog">
    <NavBar/>
    <ProgressBar/>
    <ToolBar/>

    <main class="main-content">
      <TranslationTable/>
    </main>

    <footer class="pagination-bar">
      <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
          background
          size="small">
      </el-pagination>
    </footer>

    <el-button
        class="back-to-top-btn"
        v-show="showFab"
        @click="handleBackToTop"
        :icon="Top"
        circle
        size="default"
        :title="t('Back to top')">
    </el-button>

    <ChatDrawer/>
    <HistoryDrawer/>
  </div>
</template>

<script setup>
import {onMounted, onBeforeUnmount} from 'vue'
import {Top} from '@element-plus/icons-vue'
import {showAuthDialog, checkSessionAndInit, t} from './stores/auth.js'
import {isDark, showFab, scrollToTop, toastShow} from './stores/ui.js'
import {
  currentPage, pageSize, total, onPageChange, onPageSizeChange,
  activeRowId, toggleActiveStatus, requestActiveAI, navigateNext,
  fetchData, searchQuery, tableData, cleanupProject,
  triggerUndo, triggerRedo
} from './stores/project.js'
import ToastContainer from './components/ToastContainer.vue'
import AuthDialog from './components/AuthDialog.vue'
import NavBar from './components/NavBar.vue'
import ProgressBar from './components/ProgressBar.vue'
import ToolBar from './components/ToolBar.vue'
import TranslationTable from './components/TranslationTable.vue'
import ChatDrawer from './components/ChatDrawer.vue'
import HistoryDrawer from './components/HistoryDrawer.vue'
import ShortcutsDialog from './components/ShortcutsDialog.vue'

onMounted(() => {
  checkSessionAndInit()
  window.addEventListener('scroll', handleWindowScroll)
  window.addEventListener('resize', setVHToken)
  window.addEventListener('keydown', handleKeyDown)
  setVHToken()
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', handleWindowScroll)
  window.removeEventListener('resize', setVHToken)
  window.removeEventListener('keydown', handleKeyDown)
  cleanupStore()
})

const setVHToken = () => {
  document.documentElement.style.setProperty('--vh', `${window.innerHeight * 0.01}px`)
}

const handleWindowScroll = () => {
  showFab.value = window.scrollY > 200
}

const handleBackToTop = (e) => {
  scrollToTop()
  e.currentTarget?.blur()
}

const handleKeyDown = (e) => {
  const isInput = ['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)
  const isEditingTranslation = document.activeElement.classList.contains('el-textarea__inner')
  if (isInput && !isEditingTranslation) return

  const isCtrl = e.ctrlKey || e.metaKey
  const isShift = e.shiftKey

  if (isCtrl && e.key.toLowerCase() === 'r') {
    e.preventDefault(); toggleActiveStatus('reviewed')
  }
  if (isCtrl && !isShift && e.key.toLowerCase() === 'f') {
    e.preventDefault(); toggleActiveStatus('fuzzy')
  }
  if (isCtrl && e.key === 'Enter') {
    e.preventDefault(); navigateNext('untranslated')
  }
  if (isCtrl && e.key.toLowerCase() === 't') {
    e.preventDefault(); requestActiveAI()
  }
  if (e.key === 'F5') {
    e.preventDefault(); fetchData()
  }
  if (isCtrl && isShift && e.key.toLowerCase() === 'c') {
    const item = tableData.value.find(r => r.id === activeRowId.value)
    if (item) {
      e.preventDefault(); navigator.clipboard.writeText(item.source); toastShow(t('Source copied'), 'success')
    }
  }
  
  if (isCtrl && e.key.toLowerCase() === 'z') {
    e.preventDefault();
    if (isShift) triggerRedo(); else triggerUndo();
  }
  if (isCtrl && !isShift && e.key.toLowerCase() === 'y') {
    e.preventDefault(); triggerRedo();
  }
}
</script>