<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <ToastContainer/>
  <AuthDialog/>

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

      <el-button
          class="back-to-top-btn"
          v-show="showFab"
          @click="scrollToTop"
          :icon="Top"
          circle
          size="small"
          :title="t('Back to top')">
      </el-button>
    </footer>

    <ChatDrawer/>
  </div>
</template>

<script setup>
import {onMounted, onBeforeUnmount} from 'vue'
import {Top} from '@element-plus/icons-vue'
import {
  showAuthDialog, applyTheme, isDark, checkSessionAndInit, showFab, cleanupStore,
  currentPage, pageSize, total, onPageChange, onPageSizeChange, scrollToTop, t
} from './store.js'

import ToastContainer from './components/ToastContainer.vue'
import AuthDialog from './components/AuthDialog.vue'
import NavBar from './components/NavBar.vue'
import ProgressBar from './components/ProgressBar.vue'
import ToolBar from './components/ToolBar.vue'
import TranslationTable from './components/TranslationTable.vue'
import ChatDrawer from './components/ChatDrawer.vue'

onMounted(() => {
  applyTheme(isDark.value)
  checkSessionAndInit()
  window.addEventListener('scroll', handleWindowScroll)
})

const handleWindowScroll = () => {
  showFab.value = window.scrollY > 200
}

onBeforeUnmount(() => {
  window.removeEventListener('scroll', handleWindowScroll)
  cleanupStore()
})
</script>