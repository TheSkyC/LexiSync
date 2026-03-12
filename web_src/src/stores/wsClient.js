/*
 * Copyright (c) 2025, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

let _send = null
export const registerWsSend = (fn) => {
    _send = fn
}
export const wsSend = (obj) => _send?.(obj)