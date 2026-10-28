<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import axios from "axios";
import { getRanking } from "../services/api";

const activeMarket = ref("shares");
const loading = ref(false);
const error = ref("");
const items = ref([]);
const sortBy = ref("ticker");
const sortDir = ref("asc");
const search = ref("");
const page = ref(1);
const pageSize = ref(50);
const requestLimit = ref(1500);
const requestOffset = ref(0);
const ranking = ref([]);
const rankingLoading = ref(false);

const marketTabs = [
  { key: "shares", label: "Акции" },
  { key: "etf", label: "ETF/БПИФ" },
  { key: "futures", label: "Фьючерсы" },
  { key: "bonds", label: "Облигации" },
];

const loadSecurities = async () => {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await axios.get(`${import.meta.env.VITE_API_BASE_URL || "/api"}/securities`, {
      params: { market: activeMarket.value, limit: requestLimit.value, offset: requestOffset.value },
    });
    items.value = data;
  } catch (e) {
    error.value = "Не удалось загрузить список инструментов.";
    items.value = [];
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const sortedItems = computed(() => {
  const direction = sortDir.value === "asc" ? 1 : -1;
  return [...items.value].sort((a, b) => {
    const av = a[sortBy.value];
    const bv = b[sortBy.value];
    if (typeof av === "number" || typeof bv === "number") {
      return (Number(av) - Number(bv)) * direction;
    }
    return String(av || "").localeCompare(String(bv || ""), "ru") * direction;
  });
});

const filteredItems = computed(() => {
  const query = search.value.trim().toLowerCase();
  if (!query) return sortedItems.value;
  return sortedItems.value.filter((item) => {
    const ticker = String(item.ticker || "").toLowerCase();
    const name = String(item.name || "").toLowerCase();
    return ticker.includes(query) || name.includes(query);
  });
});

const totalPages = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / pageSize.value)));

const paginatedItems = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredItems.value.slice(start, start + pageSize.value);
});

const setSort = (field) => {
  if (sortBy.value === field) {
    sortDir.value = sortDir.value === "asc" ? "desc" : "asc";
  } else {
    sortBy.value = field;
    sortDir.value = field === "name" ? "asc" : "desc";
  }
};

const sortLabel = (field) => {
  if (sortBy.value !== field) return "";
  return sortDir.value === "asc" ? "↑" : "↓";
};

const prevPage = () => {
  page.value = Math.max(1, page.value - 1);
};

const nextPage = () => {
  page.value = Math.min(totalPages.value, page.value + 1);
};

const applyPresetSort = (preset) => {
  if (preset === "ticker_asc") {
    sortBy.value = "ticker";
    sortDir.value = "asc";
  } else if (preset === "volume_desc") {
    sortBy.value = "volume";
    sortDir.value = "desc";
  } else if (preset === "price_desc") {
    sortBy.value = "last_price";
    sortDir.value = "desc";
  } else if (preset === "change_desc") {
    sortBy.value = "change_percent";
    sortDir.value = "desc";
  } else if (preset === "change_asc") {
    sortBy.value = "change_percent";
    sortDir.value = "asc";
  }
};

const exportCsv = () => {
  const rows = filteredItems.value.map((item) => ({
    ticker: item.ticker ?? "",
    name: item.name ?? "",
    market: item.market ?? "",
    board: item.board ?? "",
    last_price: Number(item.last_price ?? 0).toFixed(4),
    change_percent: Number(item.change_percent ?? 0).toFixed(4),
    volume: Number(item.volume ?? 0).toFixed(2),
  }));

  const headers = ["ticker", "name", "market", "board", "last_price", "change_percent", "volume"];
  const escapeCell = (value) => `"${String(value).replaceAll('"', '""')}"`;
  const csv = [
    headers.join(","),
    ...rows.map((row) => headers.map((header) => escapeCell(row[header])).join(",")),
  ].join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const stamp = new Date().toISOString().slice(0, 19).replaceAll(":", "-");
  link.href = url;
  link.download = `moex-${activeMarket.value}-${stamp}.csv`;
  link.click();
  URL.revokeObjectURL(url);
};

const loadRanking = async () => {
  rankingLoading.value = true;
  try {
    ranking.value = await getRanking(activeMarket.value, 60, 40);
  } catch (e) {
    ranking.value = [];
    console.error(e);
  } finally {
    rankingLoading.value = false;
  }
};

watch(activeMarket, async () => {
  page.value = 1;
  requestOffset.value = 0;
  await loadSecurities();
});
watch(search, () => {
  page.value = 1;
});
watch(totalPages, (value) => {
  if (page.value > value) page.value = value;
});
onMounted(loadSecurities);
</script>

<template>
  <section class="card">
    <div class="panel-title">
      <h2>Все инструменты</h2>
      <div class="timeframes">
        <button
          v-for="tab in marketTabs"
          :key="tab.key"
          class="btn"
          :class="{ 'btn-primary': activeMarket === tab.key }"
          @click="activeMarket = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="muted">Загрузка списка...</div>
    <div v-else-if="error" class="negative">{{ error }}</div>

    <div v-else class="table-wrap">
      <div class="toolbar-row">
        <input
          v-model="search"
          class="input"
          type="text"
          placeholder="Фильтр: тикер или название"
        />
        <select v-model.number="pageSize" class="input page-size-select">
          <option :value="25">25 на странице</option>
          <option :value="50">50 на странице</option>
          <option :value="100">100 на странице</option>
        </select>
        <select v-model.number="requestLimit" class="input page-size-select" @change="loadSecurities">
          <option :value="500">Загружать 500</option>
          <option :value="1500">Загружать 1500</option>
          <option :value="3000">Загружать 3000</option>
          <option :value="5000">Загружать 5000</option>
        </select>
      </div>
      <div class="toolbar-row">
        <button class="btn" @click="applyPresetSort('ticker_asc')">По тикеру A→Я</button>
        <button class="btn" @click="applyPresetSort('volume_desc')">Топ по объему</button>
        <button class="btn" @click="applyPresetSort('price_desc')">По цене (макс)</button>
        <button class="btn" @click="applyPresetSort('change_desc')">Лидеры роста</button>
        <button class="btn" @click="applyPresetSort('change_asc')">Лидеры падения</button>
        <button class="btn" :disabled="rankingLoading" @click="loadRanking">
          {{ rankingLoading ? "Считаем..." : "Топ по риск/доходности" }}
        </button>
        <button class="btn btn-primary" @click="exportCsv">Экспорт CSV</button>
      </div>
      <p class="muted top-gap">
        Категория: {{ marketTabs.find((x) => x.key === activeMarket)?.label }} · Найдено:
        {{ filteredItems.length }} из {{ sortedItems.length }} (смещение: {{ requestOffset }})
      </p>
      <table class="market-table">
        <thead>
          <tr>
            <th class="sortable" @click="setSort('ticker')">Тикер {{ sortLabel("ticker") }}</th>
            <th class="sortable" @click="setSort('name')">Название {{ sortLabel("name") }}</th>
            <th class="sortable" @click="setSort('last_price')">Цена {{ sortLabel("last_price") }}</th>
            <th class="sortable" @click="setSort('change_percent')">% {{ sortLabel("change_percent") }}</th>
            <th class="sortable" @click="setSort('volume')">Объем {{ sortLabel("volume") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in paginatedItems" :key="`${item.market}-${item.ticker}-${item.board}`">
            <td>
              <RouterLink :to="{ name: 'security', params: { ticker: item.ticker }, query: { market: item.market } }">
                <strong>{{ item.ticker }}</strong>
              </RouterLink>
            </td>
            <td>{{ item.name }}</td>
            <td>{{ Number(item.last_price).toFixed(2) }}</td>
            <td :class="item.change_percent >= 0 ? 'positive' : 'negative'">
              {{ item.change_percent >= 0 ? "+" : "" }}{{ Number(item.change_percent).toFixed(2) }}%
            </td>
            <td>{{ Number(item.volume).toLocaleString("ru-RU") }}</td>
          </tr>
        </tbody>
      </table>

      <div class="pagination-row">
        <button class="btn" :disabled="page <= 1" @click="prevPage">Назад</button>
        <span class="muted">Страница {{ page }} из {{ totalPages }}</span>
        <button class="btn" :disabled="page >= totalPages" @click="nextPage">Вперед</button>
      </div>
      <div class="pagination-row">
        <button
          class="btn"
          :disabled="requestOffset <= 0"
          @click="requestOffset = Math.max(0, requestOffset - requestLimit); loadSecurities()"
        >
          Назад по списку
        </button>
        <button class="btn" @click="requestOffset = requestOffset + requestLimit; loadSecurities()">
          Вперед по списку
        </button>
      </div>
      <div v-if="ranking.length" class="sub-card top-gap">
        <h4>Топ-20 по риск/доходности</h4>
        <table class="market-table">
          <thead>
            <tr>
              <th>Тикер</th>
              <th>Доходность %</th>
              <th>Волатильность</th>
              <th>Шарп</th>
              <th>Скор</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in ranking" :key="`rank-${item.ticker}-${item.board}`">
              <td>
              <RouterLink :to="{ name: 'security', params: { ticker: item.ticker }, query: { market: item.market } }">
                <strong>{{ item.ticker }}</strong>
              </RouterLink>
            </td>
              <td :class="Number(item.return_pct) >= 0 ? 'positive' : 'negative'">{{ item.return_pct }}</td>
              <td>{{ item.volatility }}</td>
              <td>{{ item.sharpe }}</td>
              <td>{{ item.score }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
