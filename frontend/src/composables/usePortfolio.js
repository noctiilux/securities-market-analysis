import { ref } from "vue";
import { getPortfolioAnalysis, removePortfolioPosition, upsertPortfolioPosition } from "../services/api";

const analysis = ref(null);
const loading = ref(false);
const error = ref("");

export function usePortfolio() {
  const load = async (lookbackDays = 120) => {
    loading.value = true;
    error.value = "";
    try {
      analysis.value = await getPortfolioAnalysis(lookbackDays);
    } catch (e) {
      analysis.value = null;
      error.value = "Не удалось загрузить портфель";
      console.error(e);
    } finally {
      loading.value = false;
    }
  };

  const upsert = async (payload) => {
    await upsertPortfolioPosition(payload);
    await load();
  };

  const remove = async (ticker) => {
    await removePortfolioPosition(ticker);
    await load();
  };

  return { analysis, loading, error, load, upsert, remove };
}
