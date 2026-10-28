<script setup>
import { RouterLink } from "vue-router";
</script>

<template>
  <section class="home-page">
    <div class="home-grid">
      <div class="card">
        <h2>Что это за сайт?</h2>
        <p class="muted">
          «Анализатор рынка» — сервис для анализа ценных бумаг Московской биржи: паспорт бумаги,
          фундаментальные и технические показатели, риск-метрики и портфель с весами.
        </p>
        <div class="hero-actions">
          <RouterLink class="btn btn-primary" to="/security/SBER">Анализ бумаги</RouterLink>
          <RouterLink class="btn" to="/markets">Каталог инструментов</RouterLink>
        </div>
        <ul class="feature-list">
          <li>Паспорт бумаги: ISIN, эмитент, купон, погашение.</li>
          <li>Фундаментал: дивиденды, доходность к погашению.</li>
          <li>Риск: Шарп, бета к IMOEX, волатильность, сигналы.</li>
          <li>Портфель с весами и сводным анализом.</li>
        </ul>
      </div>

      <div class="card illustration-card">
        <svg class="hero-image" viewBox="0 0 600 320" xmlns="http://www.w3.org/2000/svg" role="img">
          <title>Иллюстрация аналитики рынка</title>
          <rect x="1" y="1" width="598" height="318" rx="16" fill="#fffaf3" stroke="#d7c4ad" />
          <path
            d="M40 250L100 210L160 220L220 170L280 190L340 120L400 140L460 90L520 100"
            stroke="#b91c1c"
            stroke-width="4"
            fill="none"
          />
          <path d="M40 270H540" stroke="#cebca8" stroke-width="2" />
          <path d="M40 80V270" stroke="#cebca8" stroke-width="2" />
          <circle cx="520" cy="100" r="6" fill="#7f1d1d" />
          <text x="40" y="45" fill="#5b2f2f" font-size="24" font-family="Arial, sans-serif">
            MOEX · Аналитика · Сигналы
          </text>
        </svg>
      </div>
    </div>

    <div class="stats-grid top-gap">
      <div class="sub-card">
        <h3>Данные онлайн</h3>
        <p class="muted">Актуальные котировки с MOEX ISS API</p>
      </div>
      <div class="sub-card">
        <h3>Каталог</h3>
        <p class="muted">Акции, облигации, ETF/БПИФ и фьючерсы</p>
      </div>
      <div class="sub-card">
        <h3>Анализ бумаг</h3>
        <p class="muted">Отчёт, фундаментал, теханализ и риск</p>
      </div>
      <div class="sub-card">
        <h3>Экспорт</h3>
        <p class="muted">Сохранение таблиц и выборок в CSV</p>
      </div>
    </div>

    <div class="card top-gap">
      <h3>Как пользоваться сайтом</h3>
      <ol class="flow-list">
        <li>Выберите тикер в «Инструментах» и откройте «Бумага» для полного отчёта.</li>
        <li>В разделе «Аналитика» смотрите график, индикаторы и сравнение бумаг.</li>
        <li>Соберите «Портфель» с долями и оцените совокупный риск.</li>
        <li>Сохраняйте избранное в профиле для быстрого доступа.</li>
      </ol>
    </div>
  </section>
</template>
