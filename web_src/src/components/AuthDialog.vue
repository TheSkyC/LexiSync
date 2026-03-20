<!--
Copyright (c) 2025-2026, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <el-dialog v-model="showAuthDialog" :title="t('Need Authentication')" width="420px" :close-on-click-modal="false"
             :show-close="false" align-center>
    <div v-if="authError" class="auth-error">{{ authError }}</div>
    <el-tabs v-model="authTab">
      <el-tab-pane :label="t('Account Login')" name="account">
        <el-form label-position="top" @keyup.enter="loginAccount">
          <el-form-item :label="t('Username')">
            <el-input v-model="loginForm.username"></el-input>
          </el-form-item>
          <el-form-item :label="t('Password')">
            <el-input v-model="loginForm.password" show-password></el-input>
          </el-form-item>
          <el-checkbox v-model="rememberMe">{{ t('Remember Me') }}</el-checkbox>
          <el-button type="primary" @click="loginAccount" style="width:100%;margin-top:15px" :loading="loading">
            {{ t('Login') }}
          </el-button>
        </el-form>
      </el-tab-pane>
      <el-tab-pane :label="t('Token Login')" name="token">
        <el-form label-position="top" @keyup.enter="loginToken">
          <el-form-item :label="t('Access Token')">
            <el-input v-model="tokenForm.token" show-password></el-input>
          </el-form-item>
          <el-form-item :label="t('Display name for collaboration')">
            <el-input v-model="tokenForm.displayName"></el-input>
          </el-form-item>
          <el-checkbox v-model="rememberMe">{{ t('Remember Me') }}</el-checkbox>
          <el-button type="primary" @click="loginToken" style="width:100%;margin-top:15px" :loading="loading">
            {{ t('Connect to Host') }}
          </el-button>
        </el-form>
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>
<script setup>
import {
  showAuthDialog,
  authError,
  authTab,
  loginForm,
  tokenForm,
  rememberMe,
  loginAccount,
  loginToken,
  t
} from '../stores/auth.js'
import {loading} from '../stores/ui.js'
</script>
<style scoped>
.auth-error {
  background: rgba(239, 68, 68, .08);
  border: 1px solid rgba(239, 68, 68, .25);
  color: #dc2626;
  font-size: 13px;
  padding: 9px 12px;
  border-radius: 7px;
  margin-bottom: 14px;
}

/* 移动端登录弹窗缩放 */
@media (max-width: 480px) {
  :deep(.el-dialog) {
    width: 92% !important;
    margin: 0 auto;
  }
}
</style>