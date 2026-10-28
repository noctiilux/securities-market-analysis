<script setup>
import { onMounted, ref } from "vue";
import { useAuth } from "../composables/useAuth";
import MetricTooltip from "../components/MetricTooltip.vue";
import { METRIC_HELP } from "../constants/metricHelp";
import { usePortfolio } from "../composables/usePortfolio";

const auth = useAuth();
const portfolio = usePortfolio();

const formTicker = ref("SBER");
const formMarket = ref("shares");
const formWeight = ref(25);
const lookbackDays = ref(120);

const submit = async () => {
  if (!auth.isAuthenticated.value) return;
  await portfolio.upsert({
    ticker: formTicker.value.toUpperCase(),
    market: formMarket.value,
    weight_pct: Number(formWeight.value),
  });
};

const remove = async (ticker) => {
  await portfolio.remove(ticker);
};

onMounted(async () => {
  if (auth.isAuthenticated.value) {
    await portfolio.load(lookbackDays.value);
  }
});

const reload = async () => {
  await portfolio.load(lookbackDays.value);
};
</script>

<template>
  <section class="card">
    <h2>Портфель</h2>
    <p class="muted">
      Добавьте бумаги с долями в портфеле (в сумме рекомендуется 100%). Система рассчитает ожидаемую
      доходность, волатильность и концентрацию.
    </p>

    <div v-if="!auth.isAuthenticated.value" class="negative top-gap">
      Войдите в аккаунт, чтобы управлять портфелем.
    </div>

    <template v-else>
      <div class="sub-card top-gap">
        <h3>Добавить позицию</h3>
        <div class="toolbar-row">
          <input v-model="formTicker" class="input" placeholder="Тикер" />
          <select v-model="formMarket" class="input page-size-select">
            <option value="shares">Акции</option>
            <option value="etf">ETF/БПИФ</option>
            <option value="bonds">Облигации</option>
            <option value="futures">Фьючерсы</option>
          </select>
          <input v-model.number="formWeight" class="input" type="number" min="0" max="100" step="1" />
          <button class="btn btn-primary" @click="submit">Сохранить</button>
        </div>
      </div>

      <div class="sub-card top-gap">
        <div class="panel-title">
          <h3>Анализ портфеля</h3>
          <button class="btn" :disabled="portfolio.loading.value" @click="reload">
            {{ portfolio.loading.value ? "Считаем..." : "Обновить" }}
          </button>
        </div>
        <select v-model.number="lookbackDays" class="input page-size-select" @change="reload">
          <option :value="60">60 дней</option>
          <option :value="120">120 дней</option>
          <option :value="180">180 дней</option>
        </select>
      </div>

      <div v-if="portfolio.error.value" class="negative top-gap">{{ portfolio.error.value }}</div>

      <template v-if="portfolio.analysis.value">
        <div class="stats-grid top-gap">
          <div class="sub-card">
            <h4>Ожидаемая доходность</h4>
            <strong>{{ portfolio.analysis.value.metrics.expected_return_pct }}%</strong>
          </div>
          <div class="sub-card">
            <h4>Волатильность портфеля</h4>
            <strong>{{ portfolio.analysis.value.metrics.portfolio_volatility }}</strong>
          </div>
          <div class="sub-card">
            <h4>Эффективных активов</h4>
            <strong>{{ portfolio.analysis.value.metrics.effective_assets }}</strong>
          </div>
          <div class="sub-card">
            <h4>Сумма весов</h4>
            <strong>{{ portfolio.analysis.value.metrics.total_weight_pct }}%</strong>
          </div>
          <div v-if="portfolio.analysis.value.metrics.var" class="sub-card">
            <h4>
              VaR 95%
              <MetricTooltip :text="METRIC_HELP.var" />
            </h4>
            <strong>День: {{ portfolio.analysis.value.metrics.var.var_daily_pct }}%</strong>
            <p class="muted">Неделя: {{ portfolio.analysis.value.metrics.var.var_weekly_pct }}%</p>
          </div>
        </div>

        <ul v-if="portfolio.analysis.value.metrics.warnings?.length" class="feature-list top-gap">
          <li v-for="w in portfolio.analysis.value.metrics.warnings" :key="w">{{ w }}</li>
        </ul>

        <div class="table-wrap top-gap">
          <table class="market-table">
            <thead>
              <tr>
                <th>Тикер</th>
                <th>Рынок</th>
                <th>Вес %</th>
                <th>Доходность %</th>
                <th>Волатильность</th>
                <th>Шарп</th>
                <th>Бета</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pos in portfolio.analysis.value.positions" :key="pos.ticker">
                <td>
                  <router-link :to="{ name: 'security', params: { ticker: pos.ticker }, query: { market: pos.market } }">
                    {{ pos.ticker }}
                  </router-link>
                </td>
                <td>{{ pos.market }}</td>
                <td>{{ pos.weight_pct }}</td>
                <td>{{ pos.return_pct ?? "—" }}</td>
                <td>{{ pos.volatility ?? "—" }}</td>
                <td>{{ pos.sharpe ?? "—" }}</td>
                <td>{{ pos.beta ?? "—" }}</td>
                <td><button class="btn" @click="remove(pos.ticker)">Удалить</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
  </section>
</template>
