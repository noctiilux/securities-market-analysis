<script setup>
import { computed, ref } from "vue";
import AnalysisPanel from "../components/AnalysisPanel.vue";
import Chart from "../components/Chart.vue";
import QuoteCard from "../components/QuoteCard.vue";
import SearchBar from "../components/SearchBar.vue";
import TickerComparePanel from "../components/TickerComparePanel.vue";
import AlertsBanner from "../components/AlertsBanner.vue";
import Watchlist from "../components/Watchlist.vue";
import WatchlistAlerts from "../components/WatchlistAlerts.vue";
import { useAuth } from "../composables/useAuth";
import { useWatchlist } from "../composables/useWatchlist";

const currentTicker = ref("SBER");
const auth = useAuth();
const { watchlist, loading, add, remove, isInWatchlist, load } = useWatchlist();

const selectedTicker = computed(() => currentTicker.value.toUpperCase());

const selectTicker = (ticker) => {
  if (ticker) currentTicker.value = ticker.toUpperCase();
};

const handleAdd = async (ticker) => {
  if (!auth.isAuthenticated.value) return;
  await add(ticker);
  await load();
};

const handleRemove = async (ticker) => {
  if (!auth.isAuthenticated.value) return;
  await remove(ticker);
  await load();
};
</script>

<template>
  <section class="layout">
    <aside class="left-column card">
      <Watchlist
        :items="watchlist"
        :loading="loading"
        :current-ticker="selectedTicker"
        :is-authenticated="auth.isAuthenticated.value"
        @select="selectTicker"
        @add="handleAdd"
        @remove="handleRemove"
      />
      <WatchlistAlerts
        :is-authenticated="auth.isAuthenticated.value"
        :current-ticker="selectedTicker"
      />
    </aside>

    <div class="center-column">
      <AlertsBanner />
      <div class="card panel-space">
        <SearchBar @select="selectTicker" />
      </div>
      <div class="card chart-wrapper">
        <Chart :ticker="selectedTicker" />
      </div>
      <div class="card top-gap">
        <AnalysisPanel :ticker="selectedTicker" />
      </div>
      <div class="card top-gap">
        <TickerComparePanel />
      </div>
    </div>

    <aside class="right-column card">
      <QuoteCard
        :ticker="selectedTicker"
        :is-in-watchlist="isInWatchlist(selectedTicker)"
        :is-authenticated="auth.isAuthenticated.value"
        @add="handleAdd"
      />
    </aside>
  </section>
</template>
