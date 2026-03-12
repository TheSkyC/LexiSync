/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import {ref, reactive, computed, nextTick} from 'vue'
import {sessionToken, currentUser, t} from './auth.js'
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

let fetchController = null
let searchTimer = null

export const progressPct = computed(() =>
    stats.total ? Math.round((stats.reviewed + stats.translated) / stats.total * 100) : 0
)
export const filterTabs = computed(() => [
    {key: 'all', label: 'All', count: stats.total},
    {key: 'untranslated', label: 'Untranslated', count: stats.untranslated},
    {key: 'fuzzy', label: 'Fuzzy', count: stats.fuzzy},
    {key: 'translated', label: 'Translated', count: stats.translated},
    {key: 'reviewed', label: 'Reviewed', count: stats.reviewed},
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
        const res = await fetch(`/api/v1/project?token=${sessionToken.value}`, {cache: 'no-store'})
        if (res.ok) {
            const d = await res.json()
            Object.assign(stats, {
                total: d.total,
                reviewed: d.reviewed,
                translated: d.translated,
                fuzzy: d.fuzzy,
                untranslated: d.untranslated
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
        const qs = `token=${sessionToken.value}`
        const status = statusFilter.value === 'all' ? '' : statusFilter.value
        const [pRes, sRes] = await Promise.all([
            fetch(`/api/v1/project?${qs}`, {signal, cache: 'no-store'}),
            fetch(`/api/v1/strings?${qs}&page=${currentPage.value}&page_size=${pageSize.value}&search=${encodeURIComponent(searchQuery.value)}&status=${status}`, {
                signal,
                cache: 'no-store'
            })
        ])
        if (!pRes.ok || !sRes.ok) throw new Error('Fetch failed')
        const pData = await pRes.json()
        Object.assign(project, pData)
        Object.assign(stats, {
            total: pData.total,
            reviewed: pData.reviewed,
            translated: pData.translated,
            fuzzy: pData.fuzzy,
            untranslated: pData.untranslated
        })
        const sData = await sRes.json()
        tableData.value = (sData.items || []).map(item => ({
            ...item,
            active_editors: globalActiveEditors[item.id] || []
        }))
        total.value = sData.total ?? 0
    } catch (e) {
        if (e.name !== 'AbortError') toastShow(t('Sync failed'), 'error')
    } finally {
        if (!signal.aborted) loading.value = false
    }
}

export const updateTranslation = async (item, pIdx = 0) => {
    if (currentUser.role === 'viewer') return
    wsSend({action: 'blur', ts_id: item.id})
    activeRowId.value = null
    const text = item.is_plural ? item.plural_translations[pIdx] : item.translation
    try {
        const res = await fetch(`/api/v1/update?token=${sessionToken.value}`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ts_id: item.id, new_text: text, plural_index: pIdx})
        })
        if (!res.ok) throw new Error()
        toastShow(t('Saved'), 'success', 1400)
    } catch (_) {
        toastShow(t('Save failed'), 'error')
    }
}

export const toggleStatus = async (item, type) => {
    if (currentUser.role === 'viewer') return
    if (type === 'reviewed' && currentUser.role === 'translator') {
        toastShow(t('Permission Denied'), 'error');
        return
    }
    const payload = {ts_id: item.id}
    if (type === 'reviewed') {
        payload.is_reviewed = !item.is_reviewed;
        if (payload.is_reviewed) payload.is_fuzzy = false
    } else {
        payload.is_fuzzy = !item.is_fuzzy;
        if (payload.is_fuzzy) payload.is_reviewed = false
    }
    try {
        const res = await fetch(`/api/v1/update?token=${sessionToken.value}`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        })
        if (!res.ok) toastShow(res.status === 403 ? t('Permission Denied') : t('Sync failed'), 'error')
    } catch (_) {
        toastShow(t('Sync failed'), 'error');
        fetchData()
    }
}

export const requestAITranslation = async (item) => {
    if (currentUser.role === 'viewer') return
    toastShow(t('AI Translate') + '...', 'info', 2000)
    try {
        const res = await fetch(`/api/v1/ai-translate?token=${sessionToken.value}`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ts_id: item.id})
        })
        if (!res.ok) throw new Error()
    } catch (_) {
        toastShow(t('Sync failed'), 'error')
    }
}

export const onEditorFocus = (row) => {
    if (currentUser.role !== 'viewer') {
        activeRowId.value = row.id;
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

export const navigateNext = (mode = 'untranslated') => {
    if (!tableData.value.length) return
    const start = tableData.value.findIndex(r => r.id === activeRowId.value) + 1
    for (let i = 0; i < tableData.value.length; i++) {
        const item = tableData.value[(start + i) % tableData.value.length]
        const match = mode === 'any'
            || (mode === 'untranslated' && !item.translation)
            || (mode === 'unreviewed' && !item.is_reviewed)
        if (!match) continue
        activeRowId.value = item.id
        nextTick(() => {
            const el = document.querySelector(`[data-row-id="${item.id}"]`)
            if (!el) return
            el.scrollIntoView({block: 'center', behavior: 'smooth'})
            el.querySelector('textarea')?.focus()
        })
        return
    }
    toastShow(t('No more items found'), 'info')
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