import { computed, ref } from "vue";
import { getMyProfile, loginUser, registerUser } from "../services/auth";

const TOKEN_KEY = "market_analyzer_token";

const token = ref(localStorage.getItem(TOKEN_KEY) || "");
const user = ref(null);
const loading = ref(false);

const isAuthenticated = computed(() => Boolean(token.value));

const setToken = (value) => {
  token.value = value || "";
  if (value) {
    localStorage.setItem(TOKEN_KEY, value);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
};

const loadMe = async () => {
  if (!token.value) {
    user.value = null;
    return null;
  }
  const profile = await getMyProfile(token.value);
  user.value = profile;
  return profile;
};

const login = async (email, password) => {
  if (loading.value) return;
  loading.value = true;
  try {
    const payload = await loginUser(email, password);
    setToken(payload.access_token);
    await loadMe();
  } catch (error) {
    setToken("");
    user.value = null;
    throw error;
  } finally {
    loading.value = false;
  }
};

const register = async (email, password) => {
  if (loading.value) return { registered: false, loggedIn: false };
  loading.value = true;
  try {
    const profile = await registerUser(email, password);
    const payload = await loginUser(email, password);
    setToken(payload.access_token);
    user.value = profile;
    try {
      await loadMe();
    } catch {
      // Профиль уже есть из ответа register — не блокируем вход.
    }
    return { registered: true, loggedIn: true };
  } catch (error) {
    setToken("");
    user.value = null;
    throw error;
  } finally {
    loading.value = false;
  }
};

const logout = () => {
  setToken("");
  user.value = null;
};

export function useAuth() {
  return {
    token,
    user,
    loading,
    isAuthenticated,
    login,
    register,
    logout,
    loadMe,
  };
}
