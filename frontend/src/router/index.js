import { createRouter, createWebHistory } from "vue-router";
import { useAuth } from "../composables/useAuth";
import CabinetPage from "../pages/CabinetPage.vue";
import ChartsPage from "../pages/ChartsPage.vue";
import HomePage from "../pages/HomePage.vue";
import LoginPage from "../pages/LoginPage.vue";
import MarketsPage from "../pages/MarketsPage.vue";
import PortfolioPage from "../pages/PortfolioPage.vue";
import ScreenerPage from "../pages/ScreenerPage.vue";
import RegisterPage from "../pages/RegisterPage.vue";
import SecurityPage from "../pages/SecurityPage.vue";

const routes = [
  { path: "/", name: "home", component: HomePage },
  { path: "/markets", name: "markets", component: MarketsPage },
  { path: "/screener", name: "screener", component: ScreenerPage },
  { path: "/security/:ticker", name: "security", component: SecurityPage, props: true },
  { path: "/charts", name: "charts", component: ChartsPage },
  { path: "/portfolio", name: "portfolio", component: PortfolioPage, meta: { requiresAuth: true } },
  { path: "/login", name: "login", component: LoginPage },
  { path: "/register", name: "register", component: RegisterPage },
  { path: "/cabinet", name: "cabinet", component: CabinetPage, meta: { requiresAuth: true } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuth();

  if (to.meta.requiresAuth && !auth.token.value) {
    return { name: "login", query: { redirect: to.fullPath } };
  }

  if (auth.token.value && !auth.user.value) {
    try {
      await Promise.race([
        auth.loadMe(),
        new Promise((_, reject) => {
          setTimeout(() => reject(new Error("profile_timeout")), 10000);
        }),
      ]);
    } catch {
      auth.logout();
      if (to.meta.requiresAuth) {
        return { name: "login", query: { redirect: to.fullPath } };
      }
    }
  }

  return true;
});

export default router;
