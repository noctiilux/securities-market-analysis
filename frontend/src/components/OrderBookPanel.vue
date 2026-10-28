<script setup>
const props = defineProps({
  board: {
    type: String,
    default: "",
  },
  bids: {
    type: Array,
    default: () => [],
  },
  asks: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
});
</script>

<template>
  <div class="orderbook-box">
    <h4>Стакан ({{ board || "-" }})</h4>
    <div v-if="loading" class="muted">Обновление стакана...</div>
    <div v-else class="orderbook-columns">
      <div>
        <div class="muted">Покупка</div>
        <div v-for="(level, idx) in bids" :key="`b-${idx}`" class="orderbook-level">
          <span>{{ Number(level.price || 0).toFixed(2) }}</span>
          <span>{{ Number(level.volume || 0).toLocaleString("ru-RU") }}</span>
        </div>
      </div>
      <div>
        <div class="muted">Продажа</div>
        <div v-for="(level, idx) in asks" :key="`a-${idx}`" class="orderbook-level">
          <span>{{ Number(level.price || 0).toFixed(2) }}</span>
          <span>{{ Number(level.volume || 0).toLocaleString("ru-RU") }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
