/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import {ref, computed, watch, onBeforeUnmount, nextTick} from 'vue'

export function useFloatingOverlay(row, hoveredRowId, activeRowId) {
  const cellRef = ref(null)
  const overlayStyle = ref({top: '0px', left: '0px'})

  const isTargetRow = computed(() =>
      row.id === activeRowId.value || row.id === hoveredRowId.value
  )

  const overlayVisible = computed(() => isTargetRow.value)

  const updatePosition = () => {
    if (!cellRef.value) return
    const rect = cellRef.value.getBoundingClientRect()
    overlayStyle.value = {top: `${rect.top}px`, left: `${rect.left}px`}
  }

  watch(isTargetRow, (isTarget) => {
    if (isTarget) {
      nextTick(updatePosition)
    }
  })

  const handleScrollResize = () => {
    if (isTargetRow.value) {
      updatePosition()
    }
  }

  window.addEventListener('scroll', handleScrollResize, {passive: true})
  window.addEventListener('resize', handleScrollResize, {passive: true})

  onBeforeUnmount(() => {
    window.removeEventListener('scroll', handleScrollResize)
    window.removeEventListener('resize', handleScrollResize)
  })

  return {
    cellRef,
    overlayStyle,
    overlayVisible,
    isTargetRow
  }
}