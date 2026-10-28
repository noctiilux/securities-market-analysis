<script setup>
import { onMounted, ref } from "vue";
import { deleteWatchlistAlert, getWatchlistAlerts, upsertWatchlistAlert } from "../services/api";

const props = defineProps({
  isAuthenticated: { type: Boolean, default: false },
  currentTicker: { type: String, default: "SBER" },
});

const alerts = ref([]);
const alertType = ref("change_pct_above");
const threshold = ref(3);

const load = async () => {
  if (!props.isAuthenticated) {
    alerts.value = [];
    return;
  }
  try {
    alerts.value = await getWatchlistAlerts();
  } catch {
    alerts.value = [];
  }
};

const save = async () => {
  if (!props.isAuthenticated) return;
  await upsertWatchlistAlert({
    ticker: props.currentTicker,
    alert_type: alertType.value,
    threshold_value: Number(threshold.value),
  });
  await load();
};

const remove = async (id) => {
  await deleteWatchlistAlert(id);
  await load();
};

onMounted(load);
defineExpose({ load });
</script>

<template>
  <div class="watch-alerts top-gap">
    <h4>Уведомления</h4>
    <p v-if="!isAuthenticated" class="muted">Войдите, чтобы настроить пороги.</p>
    <template v-else>
      <div class="toolbar-row">
        <select v-model="alertType" class="input page-size-select">
          <option value="price_above">Цена выше</option>
          <option value="price_below">Цена ниже</option>
          <option value="change_pct_above">Изменение % за день</option>
        </select>
        <input v-model.number="threshold" class="input" type="number" step="0.1" />
        <button class="btn btn-primary" type="button" @click="save">Для {{ currentTicker }}</button>
      </div>
      <ul v-if="alerts.length" class="feature-list top-gap">
        <li v-for="a in alerts" :key="a.id" class="alert-row">
          <span>{{ a.ticker }} — {{ a.alert_type }} {{ a.threshold_value }}</span>
          <button class="btn" type="button" @click="remove(a.id)">×</button>
        </li>
      </ul>
      <p v-else class="muted">Пороги не заданы. Срабатывание показывается баннером сверху.</p>
    </template>
  </div>
</template>

<style scoped>
.alert-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
</style>
