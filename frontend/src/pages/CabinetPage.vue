<script setup>
import { onMounted } from "vue";
import { RouterLink } from "vue-router";
import { useAuth } from "../composables/useAuth";
import { useWatchlist } from "../composables/useWatchlist";

const auth = useAuth();
const watchlist = useWatchlist();

onMounted(async () => {
  if (auth.isAuthenticated.value) {
    await watchlist.load();
  }
});
</script>

<template>
  <section class="card">
    <h2>Мой профиль</h2>
    <p class="muted">
      Здесь хранится ваш профиль и персональный список избранных инструментов Московской биржи.
    </p>

    <div class="cabinet-grid">
      <div class="sub-card">
        <h3>Профиль</h3>
        <p><strong>Email:</strong> {{ auth.user.value?.email || "-" }}</p>
        <p><strong>ID пользователя:</strong> {{ auth.user.value?.id || "-" }}</p>
      </div>

      <div class="sub-card">
        <h3>Портфель</h3>
        <p class="muted">Управление позициями с весами — в разделе «Портфель».</p>
        <RouterLink class="btn btn-primary" to="/portfolio">Открыть портфель</RouterLink>
      </div>

      <div class="sub-card">
        <h3>Мое избранное</h3>
        <div v-if="watchlist.loading.value" class="muted">Загрузка...</div>
        <ul v-else class="watchlist-list">
          <li v-for="ticker in watchlist.watchlist.value" :key="ticker" class="watch-item">
            <strong>{{ ticker }}</strong>
          </li>
          <li v-if="!watchlist.watchlist.value.length" class="muted">Список пока пуст.</li>
        </ul>
      </div>
    </div>
  </section>
</template>
