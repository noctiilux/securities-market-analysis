<script setup>
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { runScreener } from "../services/api";

const market = ref("shares");
const lookbackDays = ref(60);
const rsiMin = ref("");
const rsiMax = ref("");
const sharpeMin = ref("");
const sector = ref("");
const divYieldMin = ref("");
const loading = ref(false);
const searched = ref(false);
const error = ref("");
const results = ref([]);

const numOrUndef = (value) => {
  if (value === "" || value == null) return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
};

const load = async () => {
  loading.value = true;
  error.value = "";
  searched.value = true;
  try {
    results.value = await runScreener({
      market: market.value,
      lookback_days: lookbackDays.value,
      universe_size: 35,
      rsi_min: numOrUndef(rsiMin.value),
      rsi_max: numOrUndef(rsiMax.value),
      sharpe_min: numOrUndef(sharpeMin.value),
      sector: sector.value.trim() || undefined,
      div_yield_min: numOrUndef(divYieldMin.value),
    });
  } catch (e) {
    results.value = [];
    const status = e?.response?.status;
    if (status === 502) {
      error.value = "Не удалось получить данные с MOEX. Попробуйте позже.";
    } else {
      error.value = e?.response?.data?.detail || "Ошибка скринера. Проверьте, что backend запущен.";
    }
    console.error(e);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  load();
});
</script>

<template>
  <section class="card">
    <h2>Скринер бумаг</h2>
    <p class="muted">
      Отбор по RSI, Sharpe, сектору и дивидендной доходности. Сканируется ~35 ликвидных бумаг рынка
      (1–2 минуты). Оставьте фильтры пустыми, чтобы увидеть топ по Sharpe.
    </p>

    <div class="toolbar-row top-gap">
      <select v-model="market" class="input page-size-select">
        <option value="shares">Акции</option>
        <option value="etf">ETF</option>
        <option value="bonds">Облигации</option>
      </select>
      <select v-model.number="lookbackDays" class="input page-size-select">
        <option :value="60">60 дней</option>
        <option :value="120">120 дней</option>
      </select>
      <input v-model="rsiMin" class="input" type="number" placeholder="RSI min" />
      <input v-model="rsiMax" class="input" type="number" placeholder="RSI max" />
      <input v-model="sharpeMin" class="input" type="number" step="0.1" placeholder="Sharpe min" />
      <input v-model="sector" class="input" placeholder="Сектор / группа" />
      <input v-model="divYieldMin" class="input" type="number" step="0.1" placeholder="Див. % min" />
      <button class="btn btn-primary" :disabled="loading" @click="load">
        {{ loading ? "Поиск..." : "Применить" }}
      </button>
    </div>

    <div v-if="loading" class="muted top-gap">Сканируем рынок, подождите…</div>
    <div v-else-if="error" class="negative top-gap">{{ error }}</div>
    <table v-else-if="results.length" class="data-table top-gap">
      <thead>
        <tr>
          <th>Тикер</th>
          <th>Название</th>
          <th>Сектор</th>
          <th>Доходн. %</th>
          <th>Sharpe</th>
          <th>RSI</th>
          <th>Див. %</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in results" :key="row.ticker">
          <td>
            <RouterLink :to="{ name: 'security', params: { ticker: row.ticker } }">{{ row.ticker }}</RouterLink>
          </td>
          <td>{{ row.name }}</td>
          <td>{{ row.sector || "—" }}</td>
          <td>{{ row.return_pct }}</td>
          <td>{{ row.sharpe }}</td>
          <td>{{ row.rsi14?.toFixed(1) ?? "—" }}</td>
          <td>{{ row.dividend_yield_pct ?? "—" }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="searched" class="muted top-gap">
      По заданным фильтрам ничего не найдено. Ослабьте условия (например, уберите Sharpe min или снизьте его).
    </p>
    <p v-else class="muted top-gap">Нажмите «Применить» для запуска скринера.</p>
  </section>
</template>
