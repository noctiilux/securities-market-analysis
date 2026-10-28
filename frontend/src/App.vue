<script setup>
import { computed, onMounted } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import logoUrl from "./assets/logo.svg";
import { useAuth } from "./composables/useAuth";

const route = useRoute();
const router = useRouter();
const auth = useAuth();

const isGuest = computed(() => !auth.isAuthenticated.value);

const activeClass = (name) => (route.name === name ? "menu-link active" : "menu-link");

const handleLogout = () => {
  auth.logout();
  router.push({ name: "home" });
};

onMounted(() => {
  if (auth.token.value && !auth.user.value) {
    auth.loadMe().catch(() => {
      auth.logout();
    });
  }
});
</script>

<template>
  <div class="app-root">
    <header class="topbar">
      <div class="brand">
        <img :src="logoUrl" alt="Логотип Анализатора рынка" class="brand-logo" />
        <div>
          <h1>Анализатор рынка</h1>
          <p class="muted">Удобный сайт для отслеживания рынка</p>
        </div>
      </div>

      <nav class="menu">
        <RouterLink :class="activeClass('home')" to="/">О нас</RouterLink>
        <RouterLink :class="activeClass('markets')" to="/markets">Инструменты</RouterLink>
        <RouterLink :class="activeClass('screener')" to="/screener">Скринер</RouterLink>
        <RouterLink :class="activeClass('security')" to="/security/SBER">Бумага</RouterLink>
        <RouterLink :class="activeClass('charts')" to="/charts">Аналитика</RouterLink>
        <RouterLink :class="activeClass('portfolio')" to="/portfolio">Портфель</RouterLink>
        <RouterLink :class="activeClass('cabinet')" to="/cabinet">Профиль</RouterLink>
      </nav>

      <div class="auth-actions">
        <template v-if="isGuest">
          <RouterLink class="btn" to="/login">Вход</RouterLink>
          <RouterLink class="btn btn-primary" to="/register">Регистрация</RouterLink>
        </template>
        <template v-else>
          <span class="muted">{{ auth.user.value?.email }}</span>
          <button class="btn" @click="handleLogout">Выйти</button>
        </template>
      </div>
    </header>

    <main class="page-shell">
      <RouterView />
    </main>
  </div>
</template>
