<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import OrderBookPanel from "./OrderBookPanel.vue";
import { getOrderbook, getQuote } from "../services/api";

const props = defineProps({
  ticker: {
    type: String,
    required: true,
  },
  isInWatchlist: {
    type: Boolean,
    default: false,
  },
  isAuthenticated: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["add"]);

const quote = ref(null);
const orderbook = ref({ bids: [], asks: [] });
const loading = ref(false);
const loadingOrderbook = ref(false);
const error = ref("");
const selectedBoard = ref("");
const autoRefreshEnabled = ref(true);
const refreshIntervalSec = ref(10);
let orderbookTimer = null;

const stopAutoRefresh = () => {
  if (orderbookTimer) {
    clearInterval(orderbookTimer);
    orderbookTimer = null;
  }
};

const startAutoRefresh = () => {
  stopAutoRefresh();
  if (!autoRefreshEnabled.value) return;
  orderbookTimer = setInterval(async () => {
    await loadOrderbook();
  }, refreshIntervalSec.value * 1000);
};

const loadOrderbook = async () => {
  if (!props.ticker) return;
  loadingOrderbook.value = true;
  try {
    const board = selectedBoard.value || quote.value?.board;
    if (!board) return;
    orderbook.value = await getOrderbook(props.ticker, board, 10);
  } catch (e) {
    console.error(e);
  } finally {
    loadingOrderbook.value = false;
  }
};

const loadQuote = async () => {
  loading.value = true;
  error.value = "";
  try {
    quote.value = await getQuote(props.ticker, selectedBoard.value || undefined);
    if (!selectedBoard.value && quote.value?.board) {
      selectedBoard.value = quote.value.board;
    }
    await loadOrderbook();
    startAutoRefresh();
  } catch (e) {
    quote.value = null;
    orderbook.value = { bids: [], asks: [] };
    stopAutoRefresh();
    error.value = "Не удалось загрузить котировку.";
    console.error(e);
  } finally {
    loading.value = false;
  }
};

watch(
  () => props.ticker,
  async () => {
    selectedBoard.value = "";
    await loadQuote();
  },
  { immediate: true }
);
watch(selectedBoard, async (newBoard, oldBoard) => {
  if (!newBoard || newBoard === oldBoard) return;
  await loadQuote();
});
watch([autoRefreshEnabled, refreshIntervalSec], () => {
  startAutoRefresh();
});
onBeforeUnmount(() => {
  stopAutoRefresh();
});

const lastUpdate = computed(() => {
  if (!quote.value?.last_update) return "-";
  return new Date(quote.value.last_update).toLocaleString("ru-RU");
});
</script>

<template>
  <div class="quote-card">
    <h3>Информация</h3>

    <div v-if="loading" class="spinner-box">Загрузка...</div>
    <div v-else-if="error" class="negative">{{ error }}</div>

    <div v-else-if="quote" class="quote-grid">
      <div v-if="quote.available_boards?.length" class="row">
        <span>Доска:</span>
        <select v-model="selectedBoard" class="input board-select">
          <option v-for="board in quote.available_boards" :key="board" :value="board">{{ board }}</option>
        </select>
      </div>
      <div class="row"><span>Тикер:</span><strong>{{ quote.ticker }}</strong></div>
      <div class="row"><span>Название:</span><strong>{{ quote.name }}</strong></div>
      <div class="row"><span>Статус торгов:</span><strong>{{ quote.trading_status || "нет данных" }}</strong></div>
      <div class="row"><span>Источник цены:</span><strong>{{ quote.source_field || "UNKNOWN" }}</strong></div>
      <div class="row"><span>Цена:</span><strong>{{ quote.current_price.toFixed(2) }} ₽</strong></div>
      <div class="row">
        <span>Изменение:</span>
        <strong :class="quote.change >= 0 ? 'positive' : 'negative'">
          {{ quote.change >= 0 ? "+" : "" }}{{ quote.change.toFixed(2) }} ₽
        </strong>
      </div>
      <div class="row">
        <span>%:</span>
        <strong :class="quote.change_percent >= 0 ? 'positive' : 'negative'">
          {{ quote.change_percent >= 0 ? "+" : "" }}{{ quote.change_percent.toFixed(2) }}%
        </strong>
      </div>
      <div class="row"><span>Объем:</span><strong>{{ Number(quote.volume).toLocaleString("ru-RU") }}</strong></div>
      <div class="row"><span>Оборот:</span><strong>{{ Number(quote.turnover).toLocaleString("ru-RU") }} ₽</strong></div>
      <div class="row"><span>Сделки:</span><strong>{{ Number(quote.num_trades).toLocaleString("ru-RU") }}</strong></div>
      <div class="row"><span>Средняя цена (VWAP):</span><strong>{{ Number(quote.vwap).toFixed(2) }} ₽</strong></div>
      <div class="row">
        <span>Капитализация:</span>
        <strong>{{ Number(quote.capitalization).toLocaleString("ru-RU") }} ₽</strong>
      </div>
      <div class="row"><span>Обновлено:</span><strong>{{ lastUpdate }}</strong></div>

      <div class="orderbook-controls">
        <label class="control-inline">
          <input v-model="autoRefreshEnabled" type="checkbox" />
          Автообновление стакана
        </label>
        <div class="orderbook-actions">
          <select v-model.number="refreshIntervalSec" class="input board-select" :disabled="!autoRefreshEnabled">
            <option :value="5">5 сек</option>
            <option :value="10">10 сек</option>
            <option :value="30">30 сек</option>
          </select>
          <button class="btn" :disabled="loadingOrderbook" @click="loadOrderbook">
            {{ loadingOrderbook ? "Обновление..." : "Обновить сейчас" }}
          </button>
        </div>
      </div>

      <OrderBookPanel
        :board="selectedBoard || quote.board"
        :bids="orderbook.bids"
        :asks="orderbook.asks"
        :loading="loadingOrderbook"
      />

      <button
        v-if="isAuthenticated && !isInWatchlist"
        class="btn btn-primary full-width"
        @click="emit('add', ticker)"
      >
        Добавить в избранное
      </button>
      <div v-else-if="isAuthenticated" class="muted">Тикер уже в избранном.</div>
      <div v-else class="muted">Войдите в аккаунт, чтобы добавлять в избранное.</div>
    </div>
  </div>
</template>
