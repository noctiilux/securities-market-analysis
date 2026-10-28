import axios from "axios";

const authApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 15000,
});

export const registerUser = async (email, password) => {
  const { data } = await authApi.post("/auth/register", { email, password });
  return data;
};

export const loginUser = async (email, password) => {
  const { data } = await authApi.post("/auth/login", { email, password });
  return data;
};

export const getMyProfile = async (token) => {
  const { data } = await authApi.get("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  return data;
};
