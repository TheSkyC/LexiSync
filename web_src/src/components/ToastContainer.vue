<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="toast-container" :class="shiftClass">
    <div
        v-for="t in toasts"
        :key="t.id"
        :class="[
          'toast',
          `t-${t.type}`,
          {
            'toast-leaving'       : t.leaving,
            'toast-nudge'         : t.nudge,
            'toast-settled'       : t.settled,
            'toast-swipe-out-left': t._swipeDismissDir === 'left',
            'toast-swipe-out-right':t._swipeDismissDir === 'right',
            'toast-swipe-return'  : t._swipeTransition,
          }
        ]"
        :style="getSwipeStyle(t)"
        @mouseenter="toastPause(t.id)"
        @mouseleave="toastResume(t.id)"
        @pointerdown="onPointerDown(t.id, $event)"
        @pointermove="onPointerMove(t.id, $event)"
        @pointerup="onPointerUp(t.id)"
        @pointercancel="onPointerCancel(t.id)"
    >
      <!-- 状态图标 -->
      <svg class="toast-icon" viewBox="0 0 20 20">
        <path v-if="t.type==='success'"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"/>
        <path v-else-if="t.type==='error'"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414-1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"/>
        <path v-else-if="t.type==='warning'"
              d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"/>
        <path v-else
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"/>
      </svg>

      <!-- 消息内容 -->
      <div class="toast-body">{{ t.message }}</div>

      <!--
        倒计时圆环关闭按钮
        `:key` 绑定 timerKey，使 dedupeKey 更新时强制重建 SVG，重启 CSS 动画
      -->
      <button
          v-if="t.duration > 0"
          class="toast-ring-btn"
          :class="`ring-${t.type}`"
          @click="toastDismiss(t.id)"
          title="Dismiss"
      >
        <svg
            class="ring-svg"
            viewBox="0 0 24 24"
            :key="'ring-' + t.id + '-' + t.timerKey"
        >
          <!-- 背景轨道 -->
          <circle class="ring-track" cx="12" cy="12" r="9"/>
          <!-- 倒计时圆弧，:style 设置动画时长，class 控制暂停 -->
          <circle
              class="ring-progress"
              :class="{ 'ring-paused': t.paused }"
              :style="{ animationDuration: t.remaining + 'ms' }"
              cx="12" cy="12" r="9"
          />
        </svg>
        <!-- 中心关闭图标 -->
        <svg class="ring-x-icon" viewBox="0 0 10 10">
          <line x1="2" y1="2" x2="8" y2="8" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="8" y1="2" x2="2" y2="8" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>

      <button
          v-else
          class="toast-close-btn"
          @click="toastDismiss(t.id)"
      >
        <svg viewBox="0 0 10 10" width="10" height="10">
          <line x1="2" y1="2" x2="8" y2="8" stroke-width="1.5" stroke-linecap="round" stroke="currentColor"/>
          <line x1="8" y1="2" x2="2" y2="8" stroke-width="1.5" stroke-linecap="round" stroke="currentColor"/>
        </svg>
      </button>

      <!-- 移动端滑动提示指示器 -->
      <div class="swipe-hint" :class="{ visible: t._swiping }" aria-hidden="true"></div>
    </div>
  </div>
</template>

<script setup>
import {computed} from 'vue'
import {toasts, toastDismiss, toastPause, toastResume, isHistoryOpen, isNavMenuOpen} from '../stores/ui.js'
import {isChatOpen, isUsersOpen} from '../stores/realtime.js'

// ── Drawer shift ─────────────────────────────────────────────────────────────
const isRealDrawerOpen = computed(() =>
    isChatOpen.value || isUsersOpen.value || isHistoryOpen.value
)
const shiftClass = computed(() => {
  if (isRealDrawerOpen.value) return 'is-shifted-drawer'
  if (isNavMenuOpen.value) return 'is-shifted-menu'
  return ''
})

// ── Swipe-to-dismiss ──────────────────────────────────────────────────────────
// Threshold (px) to commit a dismiss
const SWIPE_THRESHOLD = 72
// At this distance the item is fully transparent
const SWIPE_FADE_RANGE = 140
const touchMap = new Map()
const onPointerDown = (id, e) => {
  if (e.pointerType === 'mouse' && e.button !== 0) return
  e.target.setPointerCapture(e.pointerId)

  touchMap.set(id, {
    startX: e.clientX,
    startY: e.clientY,
    lastX: e.clientX,
    dir: null,
  })
  toastPause(id)
}

const onPointerMove = (id, e) => {
  const state = touchMap.get(id)
  if (!state) return

  const dx = e.clientX - state.startX
  const dy = e.clientY - state.startY
  state.lastX = e.clientX

  if (!state.dir) {
    if (Math.abs(dx) < 4 && Math.abs(dy) < 4) return
    state.dir = Math.abs(dx) >= Math.abs(dy) ? 'x' : 'y'
  }

  if (state.dir === 'y') return

  e.preventDefault()

  const item = toasts.value.find(x => x.id === id)
  if (!item || item.leaving || item._swipeDismissDir) return

  item._swipeX = dx
  item._swiping = true
}

const onPointerUp = (id) => {
  const state = touchMap.get(id)
  touchMap.delete(id)

  const item = toasts.value.find(x => x.id === id)
  if (!item) return

  if (!state || state.dir !== 'x') {
    item._swipeX = 0
    item._swiping = false
    toastResume(id)
    return
  }

  item._swiping = false
  const dx = item._swipeX ?? 0

  if (Math.abs(dx) >= SWIPE_THRESHOLD) {
    item._swipeDismissDir = dx < 0 ? 'left' : 'right'
    setTimeout(() => toastDismiss(id), 240)
  } else {
    item._swipeTransition = true
    item._swipeX = 0
    setTimeout(() => {
      const t = toasts.value.find(x => x.id === id)
      if (t) t._swipeTransition = false
    }, 320)
    toastResume(id)
  }
}

const onPointerCancel = (id) => {
  touchMap.delete(id)
  const item = toasts.value.find(x => x.id === id)
  if (!item) return
  item._swipeX = 0
  item._swiping = false
  item._swipeTransition = true
  setTimeout(() => {
    const t = toasts.value.find(x => x.id === id)
    if (t) t._swipeTransition = false
  }, 320)
  toastResume(id)
}

const getSwipeStyle = (t) => {
  if (t._swipeDismissDir || t.leaving) {
    const dx = t._swipeX ?? 0
    return dx !== 0 ? {'--toast-swipe-from': `${dx}px`} : {}
  }

  const dx = t._swipeX ?? 0
  if (dx === 0 && !t._swipeTransition) return {}

  const opacity = Math.max(0, 1 - Math.abs(dx) / SWIPE_FADE_RANGE)
  return {
    transform: `translateX(${dx}px)`,
    opacity: opacity.toFixed(3),
    willChange: 'transform, opacity',
  }
}
</script>

<style scoped>
/* ── 容器 ─────────────────────────────────────────────────────── */
.toast-container {
  position: fixed;
  top: 70px;
  right: 18px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
  max-width: 360px;
  transition: right 0.3s cubic-bezier(0.7, 0.3, 0.1, 1);
}

.toast-container.is-shifted-drawer {
  right: 410px;
}

.toast-container.is-shifted-menu {
  right: 190px;
}

/* ── Toast 条目 ───────────────────────────────────────────────── */
.toast {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
  box-shadow: var(--sh-lg);
  pointer-events: auto;
  animation: toast-in .3s both;
  touch-action: pan-y;
  user-select: none;
  -webkit-user-select: none;

  --toast-swipe-from: 0px;
}

@supports (backdrop-filter: blur(10px)) {
  .toast {
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
  }

  html.dark .toast {
    background: rgba(22, 25, 32, 0.88);
  }
}

.toast.toast-leaving {
  animation: toast-out .25s forwards;
}

/* 原地更新动效 */
.toast.toast-settled:not(.toast-nudge):not(.toast-leaving) {
  animation: none;
}

.toast.toast-nudge {
  animation: toast-nudge 0.38s ease-out !important;
}

/* ── 滑动关闭动画 ─────────────────────────────────────────────── */
.toast.toast-swipe-out-right {
  animation: toast-swipe-right 0.24s cubic-bezier(0.4, 0, 1, 1) forwards !important;
}

.toast.toast-swipe-out-left {
  animation: toast-swipe-left 0.24s cubic-bezier(0.4, 0, 1, 1) forwards !important;
}

/* 弹回过渡 */
.toast.toast-swipe-return {
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1),
  opacity 0.25s ease !important;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(24px) scale(.95);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@keyframes toast-out {
  to {
    opacity: 0;
    transform: translateX(24px) scale(.93);
  }
}

@keyframes toast-nudge {
  0% {
    transform: scale(1);
    box-shadow: var(--sh-lg);
  }
  45% {
    transform: scale(1.028);
    box-shadow: var(--sh-lg), 0 0 0 3px rgba(64, 158, 255, 0.28);
  }
  100% {
    transform: scale(1);
    box-shadow: var(--sh-lg);
  }
}

@keyframes toast-swipe-right {
  from {
    opacity: 0.3;
    transform: translateX(var(--toast-swipe-from, 0px));
  }
  to {
    opacity: 0;
    transform: translateX(120%) scale(0.92);
  }
}

@keyframes toast-swipe-left {
  from {
    opacity: 0.3;
    transform: translateX(var(--toast-swipe-from, 0px));
  }
  to {
    opacity: 0;
    transform: translateX(-120%) scale(0.92);
  }
}

/* ── 状态图标 ─────────────────────────────────────────────────── */
.toast-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  fill: currentColor;
}

/* ── 消息文字 ─────────────────────────────────────────────────── */
.toast-body {
  flex: 1;
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.4;
  word-break: break-word;
}

/* ── 倒计时圆环按钮 ───────────────────────────────────────────── */
.toast-ring-btn {
  flex-shrink: 0;
  position: relative;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background 0.18s;
}

.toast-ring-btn:hover {
  background: var(--border);
}

.ring-svg {
  position: absolute;
  inset: 0;
  width: 24px;
  height: 24px;
  transform: rotate(-90deg);
  overflow: visible;
}

.ring-track {
  fill: none;
  stroke: var(--border);
  stroke-width: 2;
}

/*
  圆弧周长：2π × 9 ≈ 56.55
  动画：dashoffset 0 → 56.55 表示从满→空
*/
.ring-progress {
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-dasharray: 56.55;
  stroke-dashoffset: 0;
  animation: ring-drain linear forwards;
  /* animationDuration 由内联 style 注入（= remaining ms） */
}

.ring-progress.ring-paused {
  animation-play-state: paused;
}

@keyframes ring-drain {
  from {
    stroke-dashoffset: 0;
  }
  to {
    stroke-dashoffset: 56.55;
  }
}

/* 中心 × 图标 */
.ring-x-icon {
  position: relative;
  z-index: 1;
  width: 10px;
  height: 10px;
  opacity: 0.55;
  stroke: currentColor;
  transition: opacity 0.15s;
  flex-shrink: 0;
}

.toast-ring-btn:hover .ring-x-icon {
  opacity: 1;
}

/* 颜色主题：继承 toast 的 color */
.t-success {
  color: var(--st-reviewed);
}

.t-error {
  color: var(--st-untranslated);
}

.t-warning {
  color: var(--st-fuzzy);
}

.t-info {
  color: var(--st-translated);
}

/* ── 无时限 toast 的普通关闭按钮 ─────────────────────────────── */
.toast-close-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 50%;
  transition: background 0.18s, color 0.18s;
  padding: 0;
}

.toast-close-btn:hover {
  background: var(--border);
  color: var(--text-main);
}

/* ── 左侧彩色边框 ─────────────────────────────────────────────── */
.toast.t-success {
  border-left: 3px solid var(--st-reviewed);
}

.toast.t-error {
  border-left: 3px solid var(--st-untranslated);
}

.toast.t-warning {
  border-left: 3px solid var(--st-fuzzy);
}

.toast.t-info {
  border-left: 3px solid var(--st-translated);
}

/* ── 移动端滑动提示轨道线 ─────────────────────────────────────── */
.swipe-hint {
  position: absolute;
  bottom: 3px;
  left: 50%;
  transform: translateX(-50%);
  width: 28px;
  height: 3px;
  border-radius: 2px;
  background: currentColor;
  opacity: 0;
  transition: opacity 0.15s, width 0.15s;
  pointer-events: none;
}

.swipe-hint.visible {
  opacity: 0.25;
  width: 40px;
}

/* ── 移动端 ───────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .toast-container {
    /* 水平居中、贴底部 */
    right: 50% !important;
    transform: translateX(50%);
    top: auto;
    bottom: 80px;
    width: 90vw;
    max-width: 400px;
    align-items: stretch;
    transition: none;
  }

  .toast-container.is-shifted-drawer,
  .toast-container.is-shifted-menu {
    right: 50% !important;
  }

  .toast {
    padding: 12px 14px;
    border-radius: 12px;
    cursor: grab;
  }

  .toast:active {
    cursor: grabbing;
  }

  /* 移动端进场：从底部升起 */
  @keyframes toast-in {
    from {
      opacity: 0;
      transform: translateY(14px) scale(.96);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }

  /* 移动端默认离场（关闭按钮）：向下消失 */
  @keyframes toast-out {
    to {
      opacity: 0;
      transform: translateY(10px) scale(.93);
    }
  }
  
  @keyframes toast-swipe-right {
    from {
      opacity: 0.3;
      transform: translateX(var(--toast-swipe-from, 0px));
    }
    to {
      opacity: 0;
      transform: translateX(110%) scale(0.94);
    }
  }

  @keyframes toast-swipe-left {
    from {
      opacity: 0.3;
      transform: translateX(var(--toast-swipe-from, 0px));
    }
    to {
      opacity: 0;
      transform: translateX(-110%) scale(0.94);
    }
  }

  .toast.toast-swipe-return {
    transition: transform 0.35s cubic-bezier(0.34, 1.8, 0.64, 1),
    opacity 0.28s ease !important;
  }
}
</style>