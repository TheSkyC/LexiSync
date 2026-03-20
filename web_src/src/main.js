/*
 * Copyright (c) 2025-2026, TheSkyC
 * SPDX-License-Identifier: Apache-2.0
 */

import {createApp} from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'

const app = createApp(App)
app.use(ElementPlus)
app.mount('#app')