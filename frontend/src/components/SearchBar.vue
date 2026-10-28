<script setup>
import { onBeforeUnmount, ref, watch } from "vue";
import { search } from "../services/api";

const emit = defineEmits(["select"]);

const query = ref("");
const results = ref([]);
const loading = ref(false);
const isOpen = ref(false);
let debounceTimer = null;

const runSearch = async () => {
  const value = query.value.trim();
  if (!value) {
    results.value = [];
    isOpen.value = false;
    return;
  }

  loading.value = true;
  try {
    results.value = await search(value);
    isOpen.value = true;
  } catch (error) {
    results.value = [];
    isOpen.value = false;
    console.error(error);
  } finally {
    loading.value = false;
  }
};

watch(query, () => {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  debounceTimer = setTimeout(runSearch, 300);
});

const pick = (ticker) => {
  emit("select", ticker);
  query.value = ticker;
  isOpen.value = false;
};

onBeforeUnmount(() => {
  if (debounceTimer) clearTimeout(debounceTimer);
});
</script>

<template>
  <div class="search-bar">
    <input
      v-model="query"
      class="input"
      type="text"
      placeholder="Поиск тикера или названия (например, SBER)"
    />

    <div v-if="loading" class="muted small-gap">Поиск...</div>

    <ul v-if="isOpen && results.length" class="dropdown">
      <li
        v-for="item in results"
        :key="item.secid"
        class="dropdown-item"
        @click="pick(item.ticker)"
      >
        <strong>{{ item.ticker }}</strong> - {{ item.name }}
      </li>
    </ul>
  </div>
</template>
