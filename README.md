# 📈 Securities Market Dynamics Analysis Application 
📋 *[Читать на русском языке](README_RU.md)*
---

A full-stack, modular web application designed for monitoring, processing, and interactively visualizing financial data from the Moscow Exchange (MOEX). The project features a client-server architecture and is fully containerized for seamless local deployment using Docker.

## 🛠️ Architecture & Tech Stack

The application is built using modern client-server standards to ensure scalability and high performance:

*   **Backend:** Python 3 + FastAPI (Asynchronous request handling, outstanding performance, and automatic Swagger UI documentation).
*   **Database & ORM:** PostgreSQL (Secure storage for users, portfolios, and price caches) + SQLAlchemy (AsyncSession pattern for non-blocking DB queries).
*   **Frontend:** Vue.js + Vue Router (Component-driven user interface, dynamic data updates without page reloads) + Axios.
*   **Data Visualization:** TradingView Lightweight Charts (Interactive candlestick and line financial charts).
*   **Security:** JWT-based authentication (Stored securely in localStorage, validated via Bearer HTTP headers) + Password hashing using Passlib (CryptContext).

## 🚀 Key Features

*   **Real-Time Data Integration:** Connected directly with the Moscow Exchange via the MOEX ISS API to fetch live quotes for stocks, bonds, futures, and ETFs.
*   **Advanced Financial Analytics:** View historical candles, trade volumes, and compute key financial metrics including return, volatility, Sharpe/Sortino ratios, and the Relative Strength Index (RSI).
*   **Investment Portfolio Management:** Assemble custom portfolios with specific asset weights, calculation of expected returns, and overall portfolio risk estimation (using VaR 95% metrics).
*   **Personal Watchlist:** Users can add financial instruments to a personalized "Favorites" section for efficient daily market tracking.
*   **Smart Alerts System:** Set specific price boundaries for selected tickers and trigger system signals when market thresholds are crossed.

## 💻 Local Setup & Deployment

To launch the full environment locally, you will need **Docker** and **Docker Compose** installed on your machine.

1. Clone this repository:
   ```bash
   git clone https://github.com
   cd securities-market-analysis
   ```

2. Build and spin up the containerized services with a single command:
   ```bash
   docker-compose up --build
   ```

Once the compilation is complete, Docker will automatically initialize the PostgreSQL database, boot up the аsynchronous Uvicorn server for the FastAPI backend, and serve the Vue.js frontend locally.

## 📁 Repository Structure

*   `/backend` — Server-side application layer.
    *   `/database` — SQLAlchemy models (`User`, `PriceCache`, `WatchlistItem`) and DB setup.
    *   `/routers` — REST API endpoints (Auth, Quotes, Portfolio, Alerts).
    *   `/services` — Core business logic, analytical engines, and the MOEX API client interface.
    *   `/tests` — Server-side unit tests powered by the `pytest` framework.
*   `/frontend` — Client-side user interface layer.
    *   `/src/components` — Reusable Vue components (Charts, Lists, Form tables).
    *   `/src/pages` — Core application views (User Dashboard, Stock Screener, Analytics Hub).
