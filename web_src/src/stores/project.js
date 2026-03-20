/*
 * Copyright (c) 2025-2026, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import {ref, reactive, computed, nextTick} from 'vue'
import {currentUser, t, authFetch, hasPermission} from './auth.js'
import {loading, toastShow} from './ui.js'
import {wsSend} from './wsClient.js'

export const tableData = ref([])
export const total = ref(0)
export const currentPage = ref(1)
export const pageSize = ref(50)
export const searchQuery = ref('')
export const statusFilter = ref('all')
export const project = reactive({name: '', source_lang: '', target_lang: ''})
export const stats = reactive({reviewed: 0, translated: 0, fuzzy: 0, untranslated: 0, total: 0})
export const activeRowId = ref(null)
export const globalActiveEditors = reactive({})
export const itemToFocus = ref(null)
export const auditHistory = reactive({undo: [], redo: []})
export const isHistoryLoading = ref(false)

let fetchController = null
let searchTimer = null

export const progressPct = computed(() =>
    stats.total ? Math.round((stats.reviewed + stats.translated) / stats.total * 100) : 0
)
export const filterTabs = computed(() => [
    {key: 'all', label: t('All'), count: stats.total},
    {key: 'untranslated', label: t('Untranslated'), count: stats.untranslated},
    {key: 'fuzzy', label: t('Fuzzy'), count: stats.fuzzy},
    {key: 'translated', label: t('Translated'), count: stats.translated},
    {key: 'reviewed', label: t('Reviewed'), count: stats.reviewed},
])

export const getStatusKey = (r) => {
    if (r.is_reviewed) return 'reviewed'
    if (r.is_fuzzy) return 'fuzzy'
    if (r.translation) return 'translated'
    return 'untranslated'
}
export const tableRowClassName = ({row}) => `row-${getStatusKey(row)}`
export const hlPh = (text) => {
    if (!text) return ''
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/(\{[^{}]+\}|%[0-9$]*[hlLzZjpt]*[a-zA-Z])/g, '<span class="hl-ph">$1</span>')
}

export const fetchProjectStats = async () => {
    try {
        const res = await authFetch('/api/v1/project', {cache: 'no-store'})
        if (res.ok) {
            const d = await res.json()
            Object.assign(stats, {
                total: d.total, reviewed: d.reviewed, translated: d.translated,
                fuzzy: d.fuzzy, untranslated: d.untranslated
            })
        }
    } catch (e) {
        console.error('Failed to sync stats:', e)
    }
}

export const fetchData = async () => {
    if (fetchController) fetchController.abort()
    fetchController = new AbortController()
    const {signal} = fetchController
    loading.value = true
    try {
        const status = statusFilter.value === 'all' ? '' : statusFilter.value
        const [pRes, sRes] = await Promise.all([
            authFetch('/api/v1/project', {signal, cache: 'no-store'}),
            authFetch(
                `/api/v1/strings?page=${currentPage.value}&page_size=${pageSize.value}` +
                `&search=${encodeURIComponent(searchQuery.value)}&status=${status}`,
                {signal, cache: 'no-store'}
            )
        ])
        if (!pRes.ok || !sRes.ok) throw new Error('Fetch failed')
        const pData = await pRes.json()
        Object.assign(project, pData)
        Object.assign(stats, {
            total: pData.total, reviewed: pData.reviewed, translated: pData.translated,
            fuzzy: pData.fuzzy, untranslated: pData.untranslated
        })
        const sData = await sRes.json()
        tableData.value = (sData.items || []).map(item => ({
            ...item,
            active_editors: globalActiveEditors[item.id] || [],
            isAiLoading: false,
            conflictData: null,
        }))
        total.value = sData.total ?? 0
    } catch (e) {
        if (e.name !== 'AbortError') toastShow(t('Sync failed'), 'error', 3000, 'sync-failed')
    } finally {
        if (!signal.aborted) loading.value = false
    }
}

export const updateTranslation = async (item, pIdx = 0) => {
    if (!hasPermission('translate')) return
    wsSend({action: 'blur', ts_id: item.id})
    activeRowId.value = null
    if (item.conflictData) item.conflictData = null

    const text = item.is_plural ? item.plural_translations[pIdx] : item.translation
    try {
        const res = await authFetch('/api/v1/update', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ts_id: item.id, new_text: text, plural_index: pIdx})
        })
        if (!res.ok) throw new Error()
        toastShow(t('Saved'), 'success', 1400, 'saved')
    } catch (_) {
        toastShow(t('Save failed'), 'error', 3000, 'save-failed')
    }
}

export const toggleStatus = async (item, type) => {
    if (type === 'reviewed' && !hasPermission('review')) {
        toastShow(t('Permission Denied'), 'error', 3000, 'permission-denied');
        return
    }
    if (type === 'fuzzy' && !hasPermission('fuzzy')) {
        toastShow(t('Permission Denied'), 'error', 3000, 'permission-denied');
        return
    }

    const payload = {ts_id: item.id}
    if (type === 'reviewed') {
        payload.is_reviewed = !item.is_reviewed
        if (payload.is_reviewed) payload.is_fuzzy = false
    } else {
        payload.is_fuzzy = !item.is_fuzzy
        if (payload.is_fuzzy) payload.is_reviewed = false
    }
    try {
        const res = await authFetch('/api/v1/update', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        })
        if (!res.ok) toastShow(res.status === 403 ? t('Permission Denied') : t('Sync failed'), 'error', 3000, res.status === 403 ? 'permission-denied' : 'sync-failed')
    } catch (_) {
        toastShow(t('Sync failed'), 'error', 3000, 'sync-failed');
        fetchData()
    }
}

export const requestAITranslation = async (item) => {
    if (!hasPermission('ai_translate')) return
    wsSend({action: 'ai_start', ts_id: item.id})
}

export const triggerUndo = async () => {
    if (!hasPermission('translate')) return
    try {
        const res = await authFetch('/api/v1/undo', {method: 'POST'})
        if (!res.ok) throw new Error(res.status === 400 ? t('Nothing to undo') : t('Sync failed'))
        toastShow(t('Undo successful'), 'success', 1500, 'undo-success')
        fetchAuditHistory()
    } catch (e) {
        toastShow(e.message, 'warning')
    }
}

export const triggerRedo = async () => {
    if (!hasPermission('translate')) return
    try {
        const res = await authFetch('/api/v1/redo', {method: 'POST'})
        if (!res.ok) throw new Error(res.status === 400 ? t('Nothing to redo') : t('Sync failed'))
        toastShow(t('Redo successful'), 'success', 1500, 'redo-success')
        fetchAuditHistory()
    } catch (e) {
        toastShow(e.message, 'warning')
    }
}

export const fetchAuditHistory = async () => {
    isHistoryLoading.value = true
    try {
        const res = await authFetch('/api/v1/history', {cache: 'no-store'})
        if (res.ok) {
            const data = await res.json()
            auditHistory.undo = data.undo_history || []
            auditHistory.redo = data.redo_history || []
        }
    } catch (e) {
        console.error('Failed to fetch history', e)
    } finally {
        isHistoryLoading.value = false
    }
}

export const onEditorFocus = (row) => {
    if (hasPermission('translate')) {
        activeRowId.value = row.id
        wsSend({action: 'focus', ts_id: row.id})
    }
}

export const setFilter = (key) => {
    statusFilter.value = key;
    currentPage.value = 1;
    fetchData()
}
export const onPageChange = () => {
    fetchData();
    document.getElementById('mainScroll')?.scrollTo(0, 0)
}
export const onPageSizeChange = (newSize) => {
    pageSize.value = newSize;
    currentPage.value = 1;
    fetchData()
}
export const handleSearch = () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
        currentPage.value = 1;
        fetchData()
    }, 450)
}

export const navigateNext = async (mode = 'untranslated') => {
    const matchesMode = (item) =>
        mode === 'any' || (mode === 'untranslated' && !item.translation) || (mode === 'unreviewed' && !item.is_reviewed)

    if (!tableData.value.length) {
        toastShow(t('No more items found'), 'info', 3000, 'navigate-info')
        return
    }

    const currentIdx = tableData.value.findIndex(r => r.id === activeRowId.value)
    const startIdx = currentIdx + 1

    for (let i = startIdx; i < tableData.value.length; i++) {
        const item = tableData.value[i]
        if (matchesMode(item)) {
            itemToFocus.value = item.id;
            return
        }
    }

    const totalPages = Math.ceil(total.value / pageSize.value)
    if (currentPage.value >= totalPages) {
        toastShow(t('Reached the last page, no more items found'), 'info', 3000, 'navigate-info')
        return
    }

    currentPage.value++
    await fetchData()
    toastShow(t('Jumped to next page'), 'info', 2500, 'navigate-info')

    const firstMatch = tableData.value.find(matchesMode)
    if (firstMatch) itemToFocus.value = firstMatch.id;
}

export const toggleActiveStatus = (type) => {
    const item = tableData.value.find(r => r.id === activeRowId.value)
    if (item) toggleStatus(item, type)
}
export const requestActiveAI = () => {
    const item = tableData.value.find(r => r.id === activeRowId.value)
    if (item) requestAITranslation(item)
}
export const cleanupProject = () => {
    clearTimeout(searchTimer);
    fetchController?.abort()
}