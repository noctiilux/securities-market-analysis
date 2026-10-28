<script setup>
import { computed, onMounted, ref, watch } from "vue";
import MetricTooltip from "./MetricTooltip.vue";
import ReturnsHistogram from "./ReturnsHistogram.vue";
import { METRIC_HELP } from "../constants/metricHelp";
import {
  compareForecastModels,
  getAnalysis,
  getBacktest,
  getReturnsDistribution,
  getWalkForwardBacktest,
} from "../services/api";

const props = defineProps({
  ticker: { type: String, required: true },
});

const loading = ref(false);
const error = ref("");
const analysis = ref(null);
const backtest = ref(null);
const forecastCompare = ref(null);
const walkForward = ref(null);
const distribution = ref(null);

const periodDays = ref(120);
const fast = ref(20);
const slow = ref(50);

const getRange = () => {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - periodDays.value);
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
};

const load = async () => {
  if (!props.ticker) return;
  loading.value = true;
  error.value = "";
  try {
    const { from, to } = getRange();
    const [a, bt, fc, wf, dist] = await Promise.all([
      getAnalysis(props.ticker, from, to),
      getBacktest(props.ticker, from, to, fast.value, slow.value),
      compareForecastModels(props.ticker, 10, periodDays.value),
      getWalkForwardBacktest(props.ticker, from, to, fast.value, slow.value),
      getReturnsDistribution(props.ticker, from, to),
    ]);
    analysis.value = a;
    backtest.value = bt;
    forecastCompare.value = fc;
    walkForward.value = wf;
    distribution.value = dist;
  } catch (e) {
    error.value = "Не удалось выполнить анализ. Попробуйте увеличить период.";
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const returnClass = computed(() =>
  Number(analysis.value?.return_pct || 0) >= 0 ? "positive" : "negative"
);

watch(() => props.ticker, load, { immediate: true });
onMounted(load);
</script>

<template>
  <div class="analysis-panel">
    <div class="panel-title">
      <h3>Разбор инструмента</h3>
      <button class="btn" :disabled="loading" @click="load">
        {{ loading ? "Обновляем..." : "Обновить" }}
      </button>
    </div>

    <div class="toolbar-row">
      <select v-model.number="periodDays" class="input page-size-select" @change="load">
        <option :value="90">90 дней</option>
        <option :value="120">120 дней</option>
        <option :value="180">180 дней</option>
        <option :value="365">365 дней</option>
      </select>
      <select v-model.number="fast" class="input page-size-select">
        <option :value="10">Fast EMA 10</option>
        <option :value="20">Fast EMA 20</option>
      </select>
      <select v-model.number="slow" class="input page-size-select">
        <option :value="50">Slow EMA 50</option>
        <option :value="100">Slow EMA 100</option>
      </select>
    </div>

    <div v-if="error" class="negative">{{ error }}</div>

    <template v-else-if="analysis && backtest">
      <div class="sub-card">
        <div class="row">
          <span>Доходность:</span>
          <strong :class="returnClass">{{ analysis.return_pct }}%</strong>
        </div>
        <div class="row">
          <span>Волатильность:<MetricTooltip :text="METRIC_HELP.volatility" /></span>
          <strong>{{ analysis.volatility }}</strong>
        </div>
        <div class="row">
          <span>Максимальная просадка:<MetricTooltip :text="METRIC_HELP.drawdown" /></span>
          <strong>{{ analysis.max_drawdown }}</strong>
        </div>
        <div class="row">
          <span>Шарп / Сортино:<MetricTooltip :text="METRIC_HELP.sharpe" /></span>
          <strong>{{ analysis.sharpe }} / {{ analysis.sortino }}</strong>
        </div>
        <div class="row">
          <span>Бета (IMOEX):<MetricTooltip :text="METRIC_HELP.beta" /></span>
          <strong>{{ analysis.beta ?? "—" }}</strong>
        </div>
        <div class="row">
          <span>RSI14:<MetricTooltip :text="METRIC_HELP.rsi" /></span>
          <strong>{{ Number(analysis.rsi14 || 0).toFixed(2) }}</strong>
        </div>
        <div class="row">
          <span>MACD:<MetricTooltip :text="METRIC_HELP.macd" /></span>
          <strong>{{ Number(analysis.macd || 0).toFixed(4) }}</strong>
        </div>
      </div>

      <ReturnsHistogram :distribution="distribution" />

      <div class="sub-card top-gap">
        <h4>Сигналы</h4>
        <ul class="feature-list">
          <li v-for="signal in analysis.signals" :key="signal">{{ signal }}</li>
        </ul>
      </div>

      <div v-if="forecastCompare?.forecast?.points?.length" class="sub-card top-gap">
        <h4>Прогноз (лучшая модель: {{ forecastCompare.best_method }})</h4>
        <div class="row">
          <span>MAPE лучшей:</span>
          <strong><MetricTooltip :text="METRIC_HELP.mape" /> {{ forecastCompare.best_mape ?? "—" }}%</strong>
        </div>
        <table class="data-table compact">
          <thead>
            <tr><th>Модель</th><th>MAPE %</th></tr>
          </thead>
          <tbody>
            <tr v-for="m in forecastCompare.models" :key="m.method">
              <td>{{ m.method }}</td>
              <td>{{ m.mape ?? "—" }}</td>
            </tr>
          </tbody>
        </table>
        <div class="row top-gap">
          <span>Ожидаемое изменение:</span>
          <strong :class="Number(forecastCompare.forecast.expected_return_pct) >= 0 ? 'positive' : 'negative'">
            {{ forecastCompare.forecast.expected_return_pct }}%
          </strong>
        </div>
      </div>

      <div class="sub-card top-gap">
        <h4>Walk-forward бэктест EMA</h4>
        <div class="row">
          <span>Средняя доходность стратегии:</span>
          <strong>{{ walkForward?.avg_strategy_return_pct ?? "—" }}%</strong>
        </div>
        <table v-if="walkForward?.periods?.length" class="data-table compact top-gap">
          <thead>
            <tr>
              <th>Период</th>
              <th>Стратегия %</th>
              <th>Buy&hold %</th>
              <th>Сделок</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in walkForward.periods" :key="i">
              <td>{{ p.from_date }} — {{ p.to_date }}</td>
              <td>{{ p.strategy_return_pct }}</td>
              <td>{{ p.buy_hold_return_pct }}</td>
              <td>{{ p.trades }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">Недостаточно данных для walk-forward.</p>
      </div>

      <div class="sub-card top-gap">
        <h4>Бэктест EMA (весь период)</h4>
        <div class="row"><span>Доходность стратегии:</span><strong>{{ backtest.strategy_return_pct }}%</strong></div>
        <div class="row"><span>Купил и держу:</span><strong>{{ backtest.buy_hold_return_pct }}%</strong></div>
        <div class="row"><span>Сделок:</span><strong>{{ backtest.trades }}</strong></div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.compact {
  font-size: 13px;
}
.compact th,
.compact td {
  padding: 4px 8px;
}
</style>
