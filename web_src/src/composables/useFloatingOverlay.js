import {ref, computed, watch, onBeforeUnmount, nextTick, onMounted} from 'vue'

export function useFloatingOverlay(row, hoveredRowId, activeRowId) {
    const cellRef = ref(null)
    const overlayStyle = ref({top: '0px', left: '0px'})
    
    const isHoveredOrActive = computed(() => {
        return row.id === activeRowId.value || row.id === hoveredRowId.value
    })

    const isTargetRow = computed(() => {
        return isHoveredOrActive.value || row.isAiLoading
    })

    const updatePosition = () => {
        if (!cellRef.value) return
        const rect = cellRef.value.getBoundingClientRect()
        overlayStyle.value = {top: `${rect.top}px`, left: `${rect.left}px`}
    }

    watch(isTargetRow, (isTarget) => {
        if (isTarget) {
            nextTick(updatePosition)
        }
    }, {immediate: true})

    onMounted(() => {
        if (isTargetRow.value) {
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
        isTargetRow,
        isHoveredOrActive
    }
}