import { onMounted, ref } from "vue";
import {
  addToWatchlist,
  getWatchlist as apiGetWatchlist,
  removeFromWatchlist,
} from "../services/api";

const watchlist = ref([]);
const loading = ref(false);

export function useWatchlist() {
  const load = async () => {
    const token = localStorage.getItem("market_analyzer_token");
    if (!token) {
      watchlist.value = [];
      return;
    }

    loading.value = true;
    try {
      watchlist.value = await apiGetWatchlist();
    } catch {
      watchlist.value = [];
    } finally {
      loading.value = false;
    }
  };

  const add = async (ticker) => {
    if (!ticker) return;
    watchlist.value = await addToWatchlist(ticker.toUpperCase());
  };

  const remove = async (ticker) => {
    if (!ticker) return;
    watchlist.value = await removeFromWatchlist(ticker.toUpperCase());
  };

  const isInWatchlist = (ticker) =>
    watchlist.value.includes((ticker || "").toUpperCase());

  onMounted(() => {
    load();
  });

  return {
    watchlist,
    loading,
    load,
    add,
    remove,
    isInWatchlist,
  };
}
