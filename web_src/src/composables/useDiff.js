/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>')
}

/**
 * 单侧 token 数量上限。超过此值直接整体标红/绿，避免大文本卡顿。
 * 原实现约 ~110（通过 12000/n 隐式限制），Myers 算法效率更高，可放宽到 300。
 */
const MAX_TOKENS = 300

/**
 * 最大允许编辑步数（Myers "D" 值）。
 * 若两段文本差异极大（D > 此值），直接退化为整体替换，
 * 避免快照数组占用过多内存（每快照 O(N+M) 空间，共 D 个）。
 */
const MAX_EDIT_DISTANCE = 160

/**
 * @param {string[]} a  左侧 token 序列
 * @param {string[]} b  右侧 token 序列
 * @returns {{ tok: string, type: 'same'|'removed'|'added' }[]}
 */
function myersDiff(a, b) {
    const n = a.length
    const m = b.length
    
    if (n === 0 && m === 0) return []
    if (n === 0) return b.map(tok => ({ tok, type: 'added' }))
    if (m === 0) return a.map(tok => ({ tok, type: 'removed' }))

    const MAX    = n + m
    const offset = MAX                          // 让负下标合法：v[k + offset]
    const v      = new Int32Array(2 * MAX + 2)  // v[k+offset] = 对角线 k 上最远 x
    const history = []                           // 每一步 d 开始前的 v 快照

    let finalD = -1

    outer:
    for (let d = 0; d <= Math.min(MAX, MAX_EDIT_DISTANCE); d++) {
        history.push(new Int32Array(v))

        for (let k = -d; k <= d; k += 2) {
            let x
            if (k === -d || (k !== d && v[k - 1 + offset] < v[k + 1 + offset])) {
                x = v[k + 1 + offset]
            } else {
                x = v[k - 1 + offset] + 1
            }

            let y = x - k
            
            while (x < n && y < m && a[x] === b[y]) { x++; y++ }

            v[k + offset] = x

            if (x >= n && y >= m) {
                finalD = d
                break outer
            }
        }
    }
    
    if (finalD === -1) {
        return [
            ...a.map(tok => ({ tok, type: 'removed' })),
            ...b.map(tok => ({ tok, type: 'added' })),
        ]
    }
    
    const reversed = []
    let x = n
    let y = m

    for (let d = finalD; d >= 1; d--) {
        const vd = history[d]
        const k  = x - y
        
        let prevK
        if (k === -d) {
            prevK = k + 1
        } else if (k === d) {
            prevK = k - 1
        } else if (vd[k - 1 + offset] < vd[k + 1 + offset]) {
            prevK = k + 1
        } else {
            prevK = k - 1
        }

        const prevX = vd[prevK + offset]
        const prevY = prevX - prevK
        
        const isInsert = (prevK === k + 1)
        const editX    = isInsert ? prevX     : prevX + 1
        const editY    = isInsert ? prevY + 1 : prevY
        
        let cx = x
        let cy = y
        while (cx > editX && cy > editY) {
            reversed.push({ tok: a[cx - 1], type: 'same' })
            cx--; cy--
        }
        
        if (isInsert) {
            reversed.push({ tok: b[editY - 1], type: 'added' })
        } else {
            reversed.push({ tok: a[editX - 1], type: 'removed' })
        }

        x = prevX
        y = prevY
    }
    
    while (x > 0 && y > 0) {
        reversed.push({ tok: a[x - 1], type: 'same' })
        x--; y--
    }

    reversed.reverse()
    return reversed
}

function renderOps(ops) {
    let html = ''
    for (const op of ops) {
        const esc = escapeHtml(op.tok)
        if (op.type === 'same') {
            html += esc
        } else if (op.type === 'removed') {
            html += `<mark class="diff-removed">${esc}</mark>`
        } else {
            html += `<mark class="diff-added">${esc}</mark>`
        }
    }
    return html
}


/**
 * 计算两段文本的词级 diff，返回带高亮标记的 HTML 字符串对。
 *
 * @param {string} textA
 * @param {string} textB
 * @returns {{ htmlA: string, htmlB: string }}
 */
export function computeDiff(textA, textB) {
    if (textA === textB) {
        const escaped = escapeHtml(textA)
        return { htmlA: escaped, htmlB: escaped }
    }

    const tokenize = (s) => s.match(/\S+|\s+/g) || []
    const tokA = tokenize(textA)
    const tokB = tokenize(textB)

    // 超出 token 上限 → 整体标红/绿，保证 UI 不卡顿
    if (tokA.length > MAX_TOKENS || tokB.length > MAX_TOKENS) {
        return {
            htmlA: `<mark class="diff-removed">${escapeHtml(textA)}</mark>`,
            htmlB: `<mark class="diff-added">${escapeHtml(textB)}</mark>`,
        }
    }

    const ops  = myersDiff(tokA, tokB)
    const opsA = ops.filter(op => op.type !== 'added')
    const opsB = ops.filter(op => op.type !== 'removed')

    return {
        htmlA: renderOps(opsA),
        htmlB: renderOps(opsB),
    }
}