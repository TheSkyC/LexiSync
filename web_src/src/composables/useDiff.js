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

export function computeDiff(textA, textB) {
    if (textA === textB) {
        const escaped = escapeHtml(textA)
        return {htmlA: escaped, htmlB: escaped}
    }

    const tokenize = (s) => s.match(/\S+|\s+/g) || []
    const tokA = tokenize(textA)
    const tokB = tokenize(textB)

    // Fallback for very long strings to avoid performance issues
    if (tokA.length * tokB.length > 12000) {
        return {
            htmlA: `<mark class="diff-removed">${escapeHtml(textA)}</mark>`,
            htmlB: `<mark class="diff-added">${escapeHtml(textB)}</mark>`,
        }
    }

    const n = tokA.length, m = tokB.length
    const dp = Array.from({length: n + 1}, () => new Uint16Array(m + 1))
    for (let i = 1; i <= n; i++) {
        for (let j = 1; j <= m; j++) {
            dp[i][j] = tokA[i - 1] === tokB[j - 1]
                ? dp[i - 1][j - 1] + 1
                : Math.max(dp[i - 1][j], dp[i][j - 1])
        }
    }

    // Traceback
    const opsA = [], opsB = []
    let i = n, j = m
    while (i > 0 || j > 0) {
        if (i > 0 && j > 0 && tokA[i - 1] === tokB[j - 1]) {
            opsA.unshift({tok: tokA[i - 1], type: 'same'})
            opsB.unshift({tok: tokB[j - 1], type: 'same'})
            i--;
            j--
        } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
            opsB.unshift({tok: tokB[j - 1], type: 'added'})
            j--
        } else {
            opsA.unshift({tok: tokA[i - 1], type: 'removed'})
            i--
        }
    }

    const render = (ops) => ops.map(op => {
        const escaped = escapeHtml(op.tok)
        if (op.type === 'same') return escaped
        if (op.type === 'removed') return `<mark class="diff-removed">${escaped}</mark>`
        return `<mark class="diff-added">${escaped}</mark>`
    }).join('')

    return {htmlA: render(opsA), htmlB: render(opsB)}
}