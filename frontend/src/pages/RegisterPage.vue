<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuth } from "../composables/useAuth";

const router = useRouter();
const auth = useAuth();

const email = ref("");
const password = ref("");
const confirmPassword = ref("");
const error = ref("");
const success = ref("");

const submit = async () => {
  error.value = "";
  success.value = "";
  if (password.value !== confirmPassword.value) {
    error.value = "Пароли не совпадают.";
    return;
  }
  try {
    const result = await auth.register(email.value, password.value);
    if (result?.loggedIn) {
      await router.push({ name: "cabinet" });
      return;
    }
    success.value = "Аккаунт создан. Выполните вход, чтобы открыть профиль.";
    await router.push({ name: "login" });
  } catch (e) {
    const status = e?.response?.status;
    if (status === 409) {
      error.value = "Пользователь с таким email уже зарегистрирован.";
      return;
    }
    error.value = e?.response?.data?.detail || "Не удалось зарегистрировать пользователя.";
  }
};
</script>

<template>
  <section class="auth-page card">
    <h2>Регистрация</h2>
    <p class="muted">Создайте аккаунт, чтобы хранить персональный список избранного.</p>

    <form class="auth-form" @submit.prevent="submit">
      <input v-model="email" class="input" type="email" placeholder="Email" required />
      <input
        v-model="password"
        class="input"
        type="password"
        placeholder="Пароль (минимум 6 символов)"
        minlength="6"
        required
      />
      <input
        v-model="confirmPassword"
        class="input"
        type="password"
        placeholder="Повторите пароль"
        minlength="6"
        required
      />
      <button class="btn btn-primary full-width" :disabled="auth.loading.value">
        {{ auth.loading.value ? "Регистрация..." : "Зарегистрироваться" }}
      </button>
    </form>

    <div v-if="success" class="positive top-gap">{{ success }}</div>
    <div v-if="error" class="negative top-gap">{{ error }}</div>
  </section>
</template>
