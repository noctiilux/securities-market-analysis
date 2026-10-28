import axios from "axios";

const api = axios.create({
  // Если задан VITE_API_BASE_URL - используем его, иначе работаем через /api (proxy в Docker/Nginx).
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 60000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("market_analyzer_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && !String(error.config?.url || "").includes("/auth/login")) {
      localStorage.removeItem("market_analyzer_token");
    }
    return Promise.reject(error);
  }
);

export const getQuote = async (ticker, board, market) => {
  const { data } = await api.get(`/quote/${ticker}`, {
    params: { ...(board ? { board } : {}), ...(market ? { market } : {}) },
  });
  return data;
};

export const getSecurityPassport = async (ticker, market) => {
  const { data } = await api.get(`/security/${ticker}`, {
    params: market ? { market } : {},
  });
  return data;
};

export const getFundamental = async (ticker, market) => {
  const { data } = await api.get(`/fundamental/${ticker}`, {
    params: market ? { market } : {},
  });
  return data;
};

export const getSecurityReport = async (ticker, from, to, market) => {
  const { data } = await api.get(`/report/${ticker}`, {
    params: { from, to, ...(market ? { market } : {}) },
  });
  return data;
};

export const getOrderbook = async (ticker, board, depth = 10) => {
  const { data } = await api.get(`/orderbook/${ticker}`, {
    params: { ...(board ? { board } : {}), depth },
  });
  return data;
};

export const getHistory = async (ticker, from, to, market) => {
  const { data } = await api.get(`/history/${ticker}`, {
    params: { from, to, ...(market ? { market } : {}) },
  });
  return data;
};

export const getForecast = async (ticker, horizon = 10, method = "ema", lookbackDays = 120) => {
  const { data } = await api.get(`/forecast/${ticker}`, {
    params: { horizon, method, lookback_days: lookbackDays, evaluate: true },
  });
  return data;
};

export const getAnalysis = async (ticker, from, to, market) => {
  const { data } = await api.get(`/analysis/${ticker}`, {
    params: { from, to, ...(market ? { market } : {}) },
  });
  return data;
};

export const getBacktest = async (ticker, from, to, fast = 20, slow = 50, market) => {
  const { data } = await api.get(`/backtest/${ticker}`, {
    params: { from, to, fast, slow, ...(market ? { market } : {}) },
  });
  return data;
};

export const getPortfolioAnalysis = async (lookbackDays = 120) => {
  const { data } = await api.get("/portfolio", { params: { lookback_days: lookbackDays } });
  return data;
};

export const upsertPortfolioPosition = async (payload) => {
  const { data } = await api.put("/portfolio", payload);
  return data;
};

export const removePortfolioPosition = async (ticker) => {
  const { data } = await api.delete(`/portfolio/${ticker}`);
  return data;
};

export const getRanking = async (market, lookback_days = 60, universe_size = 40) => {
  const { data } = await api.get("/ranking", {
    params: { market, lookback_days, universe_size },
  });
  return data;
};

export const compareTickers = async (left, right, from, to) => {
  const { data } = await api.get("/compare", {
    params: { left, right, from, to },
  });
  return data;
};

export const search = async (query) => {
  const { data } = await api.get("/search", {
    params: { query },
  });
  return data;
};

export const getWatchlist = async () => {
  const { data } = await api.get("/watchlist");
  return data;
};

export const addToWatchlist = async (ticker) => {
  const { data } = await api.post(`/watchlist/${ticker}`);
  return data;
};

export const removeFromWatchlist = async (ticker) => {
  const { data } = await api.delete(`/watchlist/${ticker}`);
  return data;
};

export const getWatchlistAlerts = async () => {
  const { data } = await api.get("/watchlist/alerts");
  return data;
};

export const upsertWatchlistAlert = async (payload) => {
  const { data } = await api.put("/watchlist/alerts", payload);
  return data;
};

export const deleteWatchlistAlert = async (alertId) => {
  const { data } = await api.delete(`/watchlist/alerts/${alertId}`);
  return data;
};

export const getTriggeredAlerts = async () => {
  const { data } = await api.get("/watchlist/alerts/triggered");
  return data;
};

export const getChartOverlays = async (ticker, from, to) => {
  const { data } = await api.get(`/chart-overlays/${ticker}`, { params: { from, to } });
  return data;
};

export const getReturnsDistribution = async (ticker, from, to) => {
  const { data } = await api.get(`/returns-distribution/${ticker}`, { params: { from, to } });
  return data;
};

export const compareForecastModels = async (ticker, horizon = 10, lookbackDays = 120) => {
  const { data } = await api.get(`/forecast/${ticker}/compare`, {
    params: { horizon, lookback_days: lookbackDays },
  });
  return data;
};

export const getWalkForwardBacktest = async (ticker, from, to, fast = 20, slow = 50) => {
  const { data } = await api.get(`/backtest/${ticker}/walkforward`, {
    params: { from, to, fast, slow },
  });
  return data;
};

export const runScreener = async (params) => {
  const { data } = await api.get("/screener", { params, timeout: 180000 });
  return data;
};

export const exportReportCsvUrl = (ticker, from, to, market) => {
  const base = import.meta.env.VITE_API_BASE_URL || "/api";
  const q = new URLSearchParams({ from, to, ...(market ? { market } : {}) });
  return `${base}/report/${ticker}/export.csv?${q}`;
};

export const exportReportPdfUrl = (ticker, from, to, market) => {
  const base = import.meta.env.VITE_API_BASE_URL || "/api";
  const q = new URLSearchParams({ from, to, ...(market ? { market } : {}) });
  return `${base}/report/${ticker}/export.pdf?${q}`;
};
