<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import { getTriggeredAlerts } from "../services/api";
import { useAuth } from "../composables/useAuth";

const auth = useAuth();
const alerts = ref([]);
let timer;

const load = async () => {
  if (!auth.isAuthenticated.value) {
    alerts.value = [];
    return;
  }
  try {
    alerts.value = await getTriggeredAlerts();
  } catch {
    alerts.value = [];
  }
};

onMounted(() => {
  load();
  timer = setInterval(load, 60000);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<template>
  <div v-if="alerts.length" class="alerts-banner">
    <strong>Уведомления по избранному:</strong>
    <ul>
      <li v-for="a in alerts" :key="a.alert_id">{{ a.message }}</li>
    </ul>
  </div>
</template>

<style scoped>
.alerts-banner {
  background: #fff3cd;
  border: 1px solid #e8c96a;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 12px;
  font-size: 14px;
}
.alerts-banner ul {
  margin: 6px 0 0;
  padding-left: 18px;
}
</style>
