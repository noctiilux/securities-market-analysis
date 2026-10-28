<script setup>
import { computed } from "vue";

const props = defineProps({
  distribution: { type: Object, default: null },
});

const maxCount = computed(() => {
  if (!props.distribution?.counts?.length) return 1;
  return Math.max(...props.distribution.counts, 1);
});
</script>

<template>
  <div v-if="distribution?.bins?.length" class="returns-hist">
    <h4>Распределение дневных доходностей</h4>
    <p class="muted">
      μ = {{ (distribution.mean * 100).toFixed(3) }}%, σ = {{ (distribution.std * 100).toFixed(3) }}%
    </p>
    <div class="bars">
      <div
        v-for="(bin, i) in distribution.bins"
        :key="i"
        class="bar-wrap"
        :title="`${(bin.from * 100).toFixed(2)}% … ${(bin.to * 100).toFixed(2)}%: ${distribution.counts[i]}`"
      >
        <div class="bar" :style="{ height: `${(distribution.counts[i] / maxCount) * 100}%` }" />
      </div>
    </div>
  </div>
  <div v-else class="muted">Нет данных для гистограммы.</div>
</template>

<style scoped>
.returns-hist {
  margin-top: 12px;
}
.bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 120px;
  margin-top: 8px;
  padding: 4px 0;
  border-bottom: 1px solid #d6c6b5;
}
.bar-wrap {
  flex: 1;
  height: 100%;
  display: flex;
  align-items: flex-end;
}
.bar {
  width: 100%;
  min-height: 2px;
  background: #4e8b57;
  border-radius: 2px 2px 0 0;
  opacity: 0.85;
}
</style>
