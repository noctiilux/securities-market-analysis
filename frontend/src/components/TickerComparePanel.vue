<script setup>
import { computed, ref } from "vue";
import { compareTickers } from "../services/api";

const leftTicker = ref("SBER");
const rightTicker = ref("GAZP");
const days = ref(120);
const loading = ref(false);
const error = ref("");
const compare = ref(null);
const chartMode = ref("normalized");

const metricWinner = (metric, lowerIsBetter = false) => {
  if (!compare.value) return null;
  const left = Number(compare.value.left?.[metric] ?? 0);
  const right = Number(compare.value.right?.[metric] ?? 0);
  if (lowerIsBetter) return left <= right ? "left" : "right";
  return left >= right ? "left" : "right";
};

const curvePoints = computed(() => {
  const curve = compare.value?.normalized_curve || [];
  if (!curve.length) {
    return { leftPolyline: "", rightPolyline: "" };
  }
  const width = 560;
  const height = 180;
  const padding = 12;
  const vals = curve.flatMap((p) =>
    chartMode.value === "normalized"
      ? [Number(p.left_norm), Number(p.right_norm)]
      : [Number(p.left_price), Number(p.right_price)]
  );
  const minV = Math.min(...vals);
  const maxV = Math.max(...vals);
  const span = Math.max(0.0001, maxV - minV);
  const toX = (idx) =>
    padding + (idx / Math.max(1, curve.length - 1)) * (width - padding * 2);
  const toY = (val) => height - padding - ((val - minV) / span) * (height - padding * 2);

  const leftPolyline = curve
    .map((p, i) =>
      `${toX(i)},${toY(Number(chartMode.value === "normalized" ? p.left_norm : p.left_price))}`
    )
    .join(" ");
  const rightPolyline = curve
    .map((p, i) =>
      `${toX(i)},${toY(Number(chartMode.value === "normalized" ? p.right_norm : p.right_price))}`
    )
    .join(" ");
  return { leftPolyline, rightPolyline };
});

const runCompare = async () => {
  loading.value = true;
  error.value = "";
  try {
    const to = new Date();
    const from = new Date();
    from.setDate(to.getDate() - days.value);
    compare.value = await compareTickers(
      leftTicker.value.toUpperCase(),
      rightTicker.value.toUpperCase(),
      from.toISOString().slice(0, 10),
      to.toISOString().slice(0, 10)
    );
  } catch (e) {
    error.value = e?.response?.data?.detail || "Не удалось сравнить тикеры.";
    compare.value = null;
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="analysis-panel">
    <div class="panel-title">
      <h3>Сравнить инструменты</h3>
      <button class="btn" :disabled="loading" @click="runCompare">
        {{ loading ? "Сравнение..." : "Сравнить" }}
      </button>
    </div>

    <div class="toolbar-row">
      <input v-model="leftTicker" class="input page-size-select" placeholder="Тикер 1 (например SBER)" />
      <input v-model="rightTicker" class="input page-size-select" placeholder="Тикер 2 (например GAZP)" />
      <select v-model.number="days" class="input page-size-select">
        <option :value="90">90 дней</option>
        <option :value="120">120 дней</option>
        <option :value="180">180 дней</option>
        <option :value="365">365 дней</option>
      </select>
    </div>

    <div v-if="error" class="negative">{{ error }}</div>
    <div v-else-if="compare" class="sub-card">
      <div class="row"><span>Лидер по доходности:</span><strong>{{ compare.leader_by_return }}</strong></div>
      <div class="row"><span>Лидер риск/доходность:</span><strong>{{ compare.leader_by_risk_adjusted }}</strong></div>
      <div class="sub-card top-gap">
        <div class="panel-title">
          <h4>{{ chartMode === "normalized" ? "Нормированная доходность (база=100)" : "Абсолютная цена" }}</h4>
          <div class="timeframes">
            <button
              class="btn"
              :class="{ 'btn-primary': chartMode === 'normalized' }"
              @click="chartMode = 'normalized'"
            >
              Нормированная
            </button>
            <button
              class="btn"
              :class="{ 'btn-primary': chartMode === 'price' }"
              @click="chartMode = 'price'"
            >
              Цена
            </button>
          </div>
        </div>
        <svg class="compare-svg" viewBox="0 0 560 180" preserveAspectRatio="none">
          <rect x="0" y="0" width="560" height="180" fill="#fffaf4" />
          <polyline :points="curvePoints.leftPolyline" fill="none" stroke="#9f1d1d" stroke-width="2.5" />
          <polyline :points="curvePoints.rightPolyline" fill="none" stroke="#1f7a3c" stroke-width="2.5" />
        </svg>
        <div class="legend-row">
          <span><strong style="color:#9f1d1d">{{ compare.left.ticker }}</strong></span>
          <span><strong style="color:#1f7a3c">{{ compare.right.ticker }}</strong></span>
        </div>
      </div>

      <table class="market-table top-gap">
        <thead>
          <tr>
            <th>Метрика</th>
            <th>{{ compare.left.ticker }}</th>
            <th>{{ compare.right.ticker }}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Доходность %</td>
            <td :class="[Number(compare.left.return_pct) >= 0 ? 'positive' : 'negative', metricWinner('return_pct') === 'left' ? 'winner-cell' : '']">{{ compare.left.return_pct }}</td>
            <td :class="[Number(compare.right.return_pct) >= 0 ? 'positive' : 'negative', metricWinner('return_pct') === 'right' ? 'winner-cell' : '']">{{ compare.right.return_pct }}</td>
          </tr>
          <tr>
            <td>Волатильность</td>
            <td :class="metricWinner('volatility', true) === 'left' ? 'winner-cell' : ''">{{ compare.left.volatility }}</td>
            <td :class="metricWinner('volatility', true) === 'right' ? 'winner-cell' : ''">{{ compare.right.volatility }}</td>
          </tr>
          <tr>
            <td>Макс. просадка</td>
            <td :class="metricWinner('max_drawdown') === 'left' ? 'winner-cell' : ''">{{ compare.left.max_drawdown }}</td>
            <td :class="metricWinner('max_drawdown') === 'right' ? 'winner-cell' : ''">{{ compare.right.max_drawdown }}</td>
          </tr>
          <tr>
            <td>RSI14</td>
            <td :class="metricWinner('rsi14') === 'left' ? 'winner-cell' : ''">{{ Number(compare.left.rsi14 || 0).toFixed(2) }}</td>
            <td :class="metricWinner('rsi14') === 'right' ? 'winner-cell' : ''">{{ Number(compare.right.rsi14 || 0).toFixed(2) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
