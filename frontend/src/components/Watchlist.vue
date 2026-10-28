<script setup>
import { onMounted, reactive, ref, watch } from "vue";
import { getQuote } from "../services/api";

const props = defineProps({
  items: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  currentTicker: {
    type: String,
    required: true,
  },
  isAuthenticated: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["select", "add", "remove"]);
const showAddInput = ref(false);
const newTicker = ref("");
const quotes = reactive({});

const loadQuotes = async () => {
  const tasks = props.items.map(async (ticker) => {
    try {
      quotes[ticker] = await getQuote(ticker);
    } catch {
      quotes[ticker] = null;
    }
  });
  await Promise.all(tasks);
};

watch(
  () => props.items.slice(),
  () => {
    loadQuotes();
  },
  { immediate: true }
);

const submitAdd = async () => {
  if (!props.isAuthenticated) return;
  const ticker = newTicker.value.trim().toUpperCase();
  if (!ticker) return;
  await emit("add", ticker);
  newTicker.value = "";
  showAddInput.value = false;
};

const removeTicker = async (ticker) => {
  if (!props.isAuthenticated) return;
  await emit("remove", ticker);
};

onMounted(loadQuotes);
</script>

<template>
  <div class="watchlist">
    <div class="panel-title">
      <h3>Избранное</h3>
      <button class="btn" :disabled="!isAuthenticated" @click="showAddInput = !showAddInput">
        Добавить
      </button>
    </div>

    <div v-if="!isAuthenticated" class="muted top-gap">
      Войдите в аккаунт, чтобы управлять избранным.
    </div>

    <div v-if="showAddInput" class="add-row">
      <input
        v-model="newTicker"
        class="input"
        type="text"
        maxlength="15"
        placeholder="Введите тикер"
        @keyup.enter="submitAdd"
      />
      <button class="btn btn-primary" @click="submitAdd">OK</button>
    </div>

    <div v-if="loading" class="muted">Загрузка избранного...</div>
    <div v-else-if="!items.length" class="muted">Избранное пока пусто.</div>

    <ul v-else class="watchlist-list">
      <li
        v-for="ticker in items"
        :key="ticker"
        class="watch-item"
        :class="{ active: ticker === currentTicker }"
        @click="emit('select', ticker)"
      >
        <div class="watch-item-head">
          <strong>{{ ticker }}</strong>
          <button
            class="remove-btn"
            title="Удалить из избранного"
            @click.stop="removeTicker(ticker)"
          >
            ×
          </button>
        </div>
        <div v-if="quotes[ticker]" class="watch-item-meta">
          <span>{{ quotes[ticker].current_price.toFixed(2) }}</span>
          <span :class="quotes[ticker].change_percent >= 0 ? 'positive' : 'negative'">
            {{ quotes[ticker].change_percent >= 0 ? "+" : "" }}{{ quotes[ticker].change_percent.toFixed(2) }}%
          </span>
        </div>
        <div v-else class="muted">Нет данных</div>
      </li>
    </ul>
  </div>
</template>
