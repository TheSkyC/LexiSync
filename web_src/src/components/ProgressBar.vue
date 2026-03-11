<!--
Copyright (c) 2025, TheSkyC
SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="progress-section" v-if="stats.total > 0">
    <div class="progress-bar-row">
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: progressPct + '%' }"></div>
      </div>
      <span class="progress-pct">{{ progressPct }}%</span>
    </div>
    <div class="progress-stats">
      <div class="ps-item"><span class="ps-dot reviewed"></span><span class="ps-val">{{
          stats.reviewed
        }}</span>&nbsp;{{ t('reviewed') }}
      </div>
      <div class="ps-item"><span class="ps-dot translated"></span><span class="ps-val">{{ stats.translated }}</span>&nbsp;{{
          t('translated')
        }}
      </div>
      <div class="ps-item"><span class="ps-dot fuzzy"></span><span class="ps-val">{{
          stats.fuzzy
        }}</span>&nbsp;{{ t('fuzzy') }}
      </div>
      <div class="ps-item"><span class="ps-dot untranslated"></span><span class="ps-val">{{ stats.untranslated }}</span>&nbsp;{{
          t('untranslated')
        }}
      </div>
      <div class="ps-item" style="margin-left:auto; color:var(--text-muted)">{{ stats.total }} {{ t('entries') }}</div>
    </div>
  </div>
</template>
<script setup>
import {stats, progressPct, t} from '../store.js'
</script>
<style scoped>
.progress-section {
  background: var(--card-bg);
  border-bottom: 1px solid var(--border);
  padding: 8px 20px;
  flex-shrink: 0;
}

.progress-bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 5px;
}

.progress-track {
  flex: 1;
  height: 5px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #22c55e);
  transition: width .6s ease;
}

.progress-pct {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-sec);
  min-width: 36px;
  text-align: right;
}

.progress-stats {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}

.ps-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--text-sec);
}

.ps-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.ps-dot.reviewed {
  background: var(--st-reviewed);
}

.ps-dot.translated {
  background: var(--st-translated);
}

.ps-dot.fuzzy {
  background: var(--st-fuzzy);
}

.ps-dot.untranslated {
  background: var(--st-untranslated);
}

.ps-val {
  font-weight: 600;
  color: var(--text-main);
}

@media (max-width: 768px) {
  .progress-section {
    padding: 8px 10px;
  }

  .progress-stats {
    gap: 8px;
  }
}
</style>