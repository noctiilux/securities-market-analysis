<script setup>
import { createChart, LineStyle } from "lightweight-charts";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { compareForecastModels, getChartOverlays, getForecast, getHistory } from "../services/api";

const props = defineProps({
  ticker: { type: String, required: true },
});

const chartContainer = ref(null);
const loading = ref(false);
const timeframe = ref("1M");
const error = ref("");
const showForecast = ref(true);
const showVolume = ref(true);
const showBollinger = ref(true);
const showLevels = ref(true);
const forecastHorizon = ref(10);
const forecastMethod = ref("auto");

let chart;
let candleSeries;
let volumeSeries;
let forecastSeries;
let upperBandSeries;
let lowerBandSeries;
let bbUpperSeries;
let bbMiddleSeries;
let bbLowerSeries;
let supportLine;
let resistanceLine;
let loadRequestId = 0;

const timeframes = [
  { key: "1D", tradingDays: 1, calendarDays: 10 },
  { key: "1W", tradingDays: 5, calendarDays: 14 },
  { key: "1M", tradingDays: 22, calendarDays: 40 },
  { key: "3M", tradingDays: 66, calendarDays: 100 },
];

const formatLocalDate = (value) => {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const getActiveTimeframe = () => timeframes.find((item) => item.key === timeframe.value) || timeframes[2];

const buildChart = () => {
  if (!chartContainer.value) return;
  chart = createChart(chartContainer.value, {
    layout: { background: { color: "#fffaf2" }, textColor: "#5d3a3a" },
    grid: { vertLines: { color: "#eadccf" }, horzLines: { color: "#eadccf" } },
    rightPriceScale: { borderColor: "#d6c6b5" },
    timeScale: { borderColor: "#d6c6b5", timeVisible: true, secondsVisible: false },
    width: chartContainer.value.clientWidth,
    height: 520,
  });

  candleSeries = chart.addCandlestickSeries({
    upColor: "#4e8b57",
    downColor: "#b33434",
    borderVisible: false,
    wickUpColor: "#4e8b57",
    wickDownColor: "#b33434",
  });

  volumeSeries = chart.addHistogramSeries({
    color: "#9ca3af",
    priceFormat: { type: "volume" },
    priceScaleId: "volume",
  });
  chart.priceScale("volume").applyOptions({
    scaleMargins: { top: 0.85, bottom: 0 },
  });

  bbUpperSeries = chart.addLineSeries({
    color: "rgba(59, 130, 246, 0.5)",
    lineWidth: 1,
    lastValueVisible: false,
    priceLineVisible: false,
  });
  bbMiddleSeries = chart.addLineSeries({
    color: "rgba(59, 130, 246, 0.8)",
    lineWidth: 1,
    lineStyle: LineStyle.Dotted,
    lastValueVisible: false,
    priceLineVisible: false,
  });
  bbLowerSeries = chart.addLineSeries({
    color: "rgba(59, 130, 246, 0.5)",
    lineWidth: 1,
    lastValueVisible: false,
    priceLineVisible: false,
  });

  upperBandSeries = chart.addLineSeries({
    color: "rgba(185, 28, 28, 0.35)",
    lineWidth: 1,
    lineStyle: LineStyle.Dotted,
    lastValueVisible: false,
    priceLineVisible: false,
  });
  lowerBandSeries = chart.addLineSeries({
    color: "rgba(185, 28, 28, 0.35)",
    lineWidth: 1,
    lineStyle: LineStyle.Dotted,
    lastValueVisible: false,
    priceLineVisible: false,
  });
  forecastSeries = chart.addLineSeries({
    color: "#b91c1c",
    lineWidth: 2,
    lineStyle: LineStyle.Dashed,
    lastValueVisible: true,
    priceLineVisible: true,
  });
};

const rangeHint = ref("");

const getDateRange = () => {
  const tf = getActiveTimeframe();
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - tf.calendarDays);
  return {
    from: formatLocalDate(from),
    to: formatLocalDate(to),
    tradingDays: tf.tradingDays,
    calendarDays: tf.calendarDays,
  };
};

const trimToTradingDays = (rows, tradingDays) => {
  if (!rows.length || rows.length <= tradingDays) return rows;
  return rows.slice(-tradingDays);
};

const clearLevelLines = () => {
  if (supportLine) {
    candleSeries.removePriceLine(supportLine);
    supportLine = null;
  }
  if (resistanceLine) {
    candleSeries.removePriceLine(resistanceLine);
    resistanceLine = null;
  }
};

const applyVisibleRange = (candles, forecastPoints) => {
  if (!chart || !candles.length) return;
  const firstTime = candles[0].time;
  let lastTime = candles[candles.length - 1].time;
  const tf = getActiveTimeframe();
  if (showForecast.value && forecastPoints?.length && tf.tradingDays >= 22) {
    lastTime = forecastPoints[forecastPoints.length - 1].date;
  }
  chart.timeScale().setVisibleRange({ from: firstTime, to: lastTime });
};

const clearForecast = () => {
  forecastSeries?.setData([]);
  upperBandSeries?.setData([]);
  lowerBandSeries?.setData([]);
};

const clearOverlays = () => {
  bbUpperSeries?.setData([]);
  bbMiddleSeries?.setData([]);
  bbLowerSeries?.setData([]);
  clearLevelLines();
};

const loadHistory = async () => {
  if (!props.ticker) return;
  if (!chart || !candleSeries) buildChart();
  if (!chart || !candleSeries) return;

  const currentRequestId = ++loadRequestId;
  loading.value = true;
  error.value = "";
  clearForecast();
  clearOverlays();

  try {
    const { from, to, tradingDays, calendarDays } = getDateRange();
    const [data, overlays] = await Promise.all([
      getHistory(props.ticker, from, to),
      getChartOverlays(props.ticker, from, to).catch(() => null),
    ]);

    let rows = data.map((item) => ({
      time: item.date,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
      volume: item.volume,
    }));
    rows = trimToTradingDays(rows, tradingDays);

    if (currentRequestId !== loadRequestId) return;

    const candles = rows.map(({ time, open, high, low, close }) => ({ time, open, high, low, close }));

    rangeHint.value = candles.length
      ? `${candles[0].time} — ${candles[candles.length - 1].time} · ${candles.length} свечей`
      : "Нет данных за выбранный период";

    candleSeries.setData(candles);

    if (showVolume.value) {
      volumeSeries.setData(
        rows.map((r) => ({
          time: r.time,
          value: r.volume || 0,
          color: r.close >= r.open ? "rgba(78, 139, 87, 0.5)" : "rgba(179, 52, 52, 0.5)",
        }))
      );
    } else {
      volumeSeries.setData([]);
    }

    if (showBollinger.value && overlays?.bollinger?.length) {
      const upper = [];
      const middle = [];
      const lower = [];
      for (const p of overlays.bollinger) {
        const d = String(p.date).slice(0, 10);
        if (!candles.find((c) => c.time === d)) continue;
        upper.push({ time: d, value: p.bb_upper });
        middle.push({ time: d, value: p.bb_middle });
        lower.push({ time: d, value: p.bb_lower });
      }
      bbUpperSeries.setData(upper);
      bbMiddleSeries.setData(middle);
      bbLowerSeries.setData(lower);
    }

    if (showLevels.value && overlays) {
      clearLevelLines();
      if (overlays.support != null) {
        supportLine = candleSeries.createPriceLine({
          price: overlays.support,
          color: "#16a34a",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          title: "Поддержка",
        });
      }
      if (overlays.resistance != null) {
        resistanceLine = candleSeries.createPriceLine({
          price: overlays.resistance,
          color: "#dc2626",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          title: "Сопротивление",
        });
      }
    }

    let forecastPoints = [];
    if (showForecast.value && candles.length > 0) {
      const lookback = Math.max(calendarDays + 30, 90);
      let method = forecastMethod.value === "auto" ? "ema" : forecastMethod.value;
      if (forecastMethod.value === "auto") {
        const cmp = await compareForecastModels(props.ticker, forecastHorizon.value, lookback);
        if (currentRequestId !== loadRequestId) return;
        method = cmp.best_method || "ema";
      }
      const forecast = await getForecast(props.ticker, forecastHorizon.value, method, lookback);
      if (currentRequestId !== loadRequestId) return;
      forecastPoints = forecast.points || [];

      const lastCandle = candles[candles.length - 1];
      const bridge = { time: lastCandle.time, value: lastCandle.close };
      forecastSeries.setData([
        bridge,
        ...forecastPoints.map((p) => ({ time: p.date, value: p.price })),
      ]);
      upperBandSeries.setData([
        bridge,
        ...forecastPoints.map((p) => ({ time: p.date, value: p.upper })),
      ]);
      lowerBandSeries.setData([
        bridge,
        ...forecastPoints.map((p) => ({ time: p.date, value: p.lower })),
      ]);
    }

    applyVisibleRange(candles, forecastPoints);
  } catch (e) {
    if (currentRequestId !== loadRequestId) return;
    error.value = "Не удалось загрузить историю.";
    candleSeries.setData([]);
    volumeSeries?.setData([]);
    clearForecast();
    clearOverlays();
    console.error(e);
  } finally {
    if (currentRequestId === loadRequestId) loading.value = false;
  }
};

const selectTimeframe = async (value) => {
  if (timeframe.value === value) return;
  timeframe.value = value;
  await loadHistory();
};

const handleResize = () => {
  if (!chart || !chartContainer.value) return;
  chart.applyOptions({ width: chartContainer.value.clientWidth });
};

onMounted(async () => {
  await nextTick();
  buildChart();
  await loadHistory();
  window.addEventListener("resize", handleResize);
});

onBeforeUnmount(() => {
  loadRequestId += 1;
  window.removeEventListener("resize", handleResize);
  if (chart) chart.remove();
});

watch(() => props.ticker, loadHistory);
watch([forecastHorizon, showVolume, showBollinger, showLevels, forecastMethod], loadHistory);
</script>

<template>
  <div class="chart-panel">
    <div class="chart-head">
      <h3>{{ ticker }} — График (MOEX)</h3>
      <div class="timeframes">
        <button
          v-for="tf in timeframes"
          :key="tf.key"
          class="btn"
          :class="{ 'btn-primary': timeframe === tf.key }"
          @click="selectTimeframe(tf.key)"
        >
          {{ tf.key }}
        </button>
      </div>
    </div>

    <div class="toolbar-row chart-tools">
      <label class="forecast-toggle"><input v-model="showVolume" type="checkbox" @change="loadHistory" /> Объём</label>
      <label class="forecast-toggle"><input v-model="showBollinger" type="checkbox" @change="loadHistory" /> Bollinger</label>
      <label class="forecast-toggle"><input v-model="showLevels" type="checkbox" @change="loadHistory" /> Уровни</label>
      <label class="forecast-toggle"><input v-model="showForecast" type="checkbox" @change="loadHistory" /> Прогноз</label>
      <select v-model="forecastMethod" class="input page-size-select" :disabled="!showForecast">
        <option value="auto">Прогноз: лучший по MAPE</option>
        <option value="ema">EMA</option>
        <option value="linear">Линейный</option>
        <option value="sma">SMA</option>
      </select>
      <select
        v-model.number="forecastHorizon"
        class="input page-size-select"
        :disabled="!showForecast"
        @change="loadHistory"
      >
        <option :value="5">5 дней</option>
        <option :value="10">10 дней</option>
        <option :value="20">20 дней</option>
      </select>
    </div>

    <div v-if="loading" class="spinner-box">Загрузка графика...</div>
    <div v-else-if="error" class="negative">{{ error }}</div>
    <div ref="chartContainer" class="chart-container chart-container-tall" />
    <div class="chart-labels muted">
      Ось X: дата. Свечи + объём. Синие линии — Bollinger, зелёная/красная пунктир — поддержка/сопротивление.
      <span v-if="rangeHint"> Период: {{ rangeHint }}.</span>
    </div>
  </div>
</template>

<style scoped>
.chart-tools {
  margin-bottom: 8px;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.forecast-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}
.chart-container-tall {
  min-height: 520px;
}
</style>
