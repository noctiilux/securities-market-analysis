<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuth } from "../composables/useAuth";

const route = useRoute();
const router = useRouter();
const auth = useAuth();

const email = ref("");
const password = ref("");
const error = ref("");

const submit = async () => {
  error.value = "";
  try {
    await auth.login(email.value, password.value);
    await router.push(route.query.redirect || "/cabinet");
  } catch (e) {
    error.value = e?.response?.data?.detail || "Не удалось выполнить вход.";
  }
};
</script>

<template>
  <section class="auth-page card">
    <h2>Вход в личный кабинет</h2>
    <p class="muted">Введите email и пароль, чтобы открыть персональное избранное.</p>

    <form class="auth-form" @submit.prevent="submit">
      <input v-model="email" class="input" type="email" placeholder="Email" required />
      <input v-model="password" class="input" type="password" placeholder="Пароль" required />
      <button class="btn btn-primary full-width" :disabled="auth.loading.value">
        {{ auth.loading.value ? "Вход..." : "Войти" }}
      </button>
    </form>

    <div v-if="error" class="negative top-gap">{{ error }}</div>
  </section>
</template>
