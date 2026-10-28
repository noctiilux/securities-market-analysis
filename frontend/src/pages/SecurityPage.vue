<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import MetricTooltip from "../components/MetricTooltip.vue";
import ReturnsHistogram from "../components/ReturnsHistogram.vue";
import SearchBar from "../components/SearchBar.vue";
import { METRIC_HELP } from "../constants/metricHelp";
import { exportReportCsvUrl, exportReportPdfUrl, getReturnsDistribution, getSecurityReport } from "../services/api";

const route = useRoute();
const router = useRouter();

const ticker = ref((route.params.ticker || "SBER").toString().toUpperCase());
const market = ref(route.query.market || "");
const periodDays = ref(180);
const loading = ref(false);
const error = ref("");
const report = ref(null);
const distribution = ref(null);

const marketLabel = computed(() => report.value?.passport?.instrument_type || "—");

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
  if (!ticker.value) return;
  loading.value = true;
  error.value = "";
  try {
    const { from, to } = getRange();
    const [rep, dist] = await Promise.all([
      getSecurityReport(ticker.value, from, to, market.value || undefined),
      getReturnsDistribution(ticker.value, from, to),
    ]);
    report.value = rep;
    distribution.value = dist;
    market.value = report.value.market;
    router.replace({
      name: "security",
      params: { ticker: ticker.value },
      query: { market: market.value },
    });
  } catch (e) {
    error.value = "Не удалось загрузить анализ бумаги. Проверьте тикер и период.";
    report.value = null;
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const onSelectTicker = (value) => {
  ticker.value = value.toUpperCase();
  market.value = "";
  load();
};

watch(
  () => route.params.ticker,
  (value) => {
    if (value) {
      ticker.value = String(value).toUpperCase();
      load();
    }
  }
);

onMounted(load);
</script>

<template>
  <section class="security-page">
    <div class="card panel-space">
      <div class="panel-title">
        <h2>Анализ ценной бумаги</h2>
        <button class="btn" :disabled="loading" @click="load">{{ loading ? "Загрузка..." : "Обновить" }}</button>
        <a
          v-if="report"
          class="btn"
          :href="exportReportCsvUrl(ticker, getRange().from, getRange().to, market || undefined)"
          target="_blank"
          rel="noopener"
        >CSV</a>
        <a
          v-if="report"
          class="btn"
          :href="exportReportPdfUrl(ticker, getRange().from, getRange().to, market || undefined)"
          target="_blank"
          rel="noopener"
        >PDF</a>
      </div>
      <div class="toolbar-row">
        <SearchBar @select="onSelectTicker" />
        <input v-model="ticker" class="input" placeholder="Тикер" @keyup.enter="load" />
        <select v-model.number="periodDays" class="input page-size-select" @change="load">
          <option :value="90">90 дней</option>
          <option :value="180">180 дней</option>
          <option :value="365">365 дней</option>
        </select>
      </div>
    </div>

    <div v-if="error" class="card negative top-gap">{{ error }}</div>

    <template v-if="report && !loading">
      <div class="security-grid top-gap">
        <div class="card">
          <h3>Паспорт бумаги</h3>
          <p class="muted">{{ report.passport.name }} · {{ marketLabel }}</p>
          <div class="row"><span>Тикер:</span><strong>{{ report.passport.ticker }}</strong></div>
          <div class="row"><span>ISIN:</span><strong>{{ report.passport.isin || "—" }}</strong></div>
          <div class="row"><span>Эмитент:</span><strong>{{ report.passport.issuer || "—" }}</strong></div>
          <div class="row"><span>Цена:</span><strong>{{ report.passport.current_price }}</strong></div>
          <div class="row"><span>Капитализация:</span><strong>{{ report.passport.capitalization || "—" }}</strong></div>
          <div v-if="report.passport.maturity_date" class="row">
            <span>Погашение:</span><strong>{{ report.passport.maturity_date }}</strong>
          </div>
          <div v-if="report.passport.coupon_percent" class="row">
            <span>Купон:</span><strong>{{ report.passport.coupon_percent }}%</strong>
          </div>
        </div>

        <div class="card">
          <h3>Фундаментальный анализ</h3>
          <div v-if="report.fundamental.dividend_yield_pct != null" class="row">
            <span>Див. доходность (12 мес.):</span>
            <strong>{{ report.fundamental.dividend_yield_pct }}%</strong>
          </div>
          <div v-if="report.fundamental.yield_to_maturity != null" class="row">
            <span>Доходность к погашению:</span>
            <strong>{{ report.fundamental.yield_to_maturity }}%</strong>
          </div>
          <div v-if="report.fundamental.accrued_interest != null" class="row">
            <span>НКД:</span><strong>{{ report.fundamental.accrued_interest }}</strong>
          </div>
          <div v-if="report.fundamental.dividends?.length" class="top-gap">
            <h4>Последние дивиденды</h4>
            <ul class="feature-list">
              <li v-for="d in report.fundamental.dividends.slice(0, 5)" :key="d.registry_date">
                {{ d.registry_date }} — {{ d.value }} {{ d.currency }}
              </li>
            </ul>
          </div>
          <p v-else class="muted">Дивидендная история недоступна или не применима.</p>
        </div>

        <div class="card">
          <h3>Технический и риск-анализ</h3>
          <div class="row">
            <span>Доходность:</span>
            <strong :class="Number(report.technical.return_pct) >= 0 ? 'positive' : 'negative'">
              {{ report.technical.return_pct }}%
            </strong>
          </div>
          <div class="row"><span>Волатильность:</span><strong>{{ report.technical.volatility }}</strong></div>
          <div class="row"><span>Шарп:</span><strong>{{ report.technical.sharpe }}</strong></div>
          <div class="row"><span>Сортино:</span><strong>{{ report.technical.sortino }}</strong></div>
          <div class="row"><span>Бета (IMOEX):</span><strong>{{ report.technical.beta ?? "—" }}</strong></div>
          <div class="row">
            <span>RSI14:<MetricTooltip :text="METRIC_HELP.rsi" /></span>
            <strong>{{ Number(report.technical.rsi14 || 0).toFixed(2) }}</strong>
          </div>
          <ReturnsHistogram :distribution="distribution" />
          <ul class="feature-list top-gap">
            <li v-for="signal in report.technical.signals" :key="signal">{{ signal }}</li>
          </ul>
        </div>

        <div v-if="report.forecast?.points?.length" class="card">
          <h3>Прогноз ({{ report.forecast.horizon }} дней)</h3>
          <div class="row">
            <span>Ожидаемое изменение:</span>
            <strong :class="Number(report.forecast.expected_return_pct) >= 0 ? 'positive' : 'negative'">
              {{ report.forecast.expected_return_pct }}%
            </strong>
          </div>
          <div class="row">
            <span>Целевая цена:</span>
            <strong>{{ report.forecast.points[report.forecast.points.length - 1].price }}</strong>
          </div>
          <div v-if="report.forecast.metrics?.mape != null" class="row">
            <span>MAPE на тесте:</span><strong>{{ report.forecast.metrics.mape }}%</strong>
          </div>
        </div>
      </div>

      <div class="card top-gap report-block">
        <h3>Заключение</h3>
        <p><strong>Уровень риска:</strong> {{ report.summary.risk_level }}</p>
        <p><strong>Рекомендация:</strong> {{ report.summary.recommendation }}</p>
        <p v-for="(paragraph, idx) in report.summary.paragraphs" :key="idx">{{ paragraph }}</p>
      </div>
    </template>
  </section>
</template>

<style scoped>
.security-page {
  display: flex;
  flex-direction: column;
}

.security-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.report-block p {
  margin: 8px 0;
}
</style>
