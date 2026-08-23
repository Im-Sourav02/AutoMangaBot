# ════════════════════════════════════════════════════════════════════════════════
#  Auto Manga Bot — Railway-ready Dockerfile
#  All browser/OS installations happen at BUILD time so startup is instant.
# ════════════════════════════════════════════════════════════════════════════════
FROM python:3.11-slim

WORKDIR /app

# ── 1. OS-level dependencies for Playwright Chromium + Camoufox (Firefox) ──────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build helpers
    git curl wget \
    # Chromium / Playwright
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libxshmfence1 libx11-6 libx11-xcb1 libxcb1 libxext6 \
    # Firefox / Camoufox
    libgtk-3-0 libdbus-glib-1-2 libxt6 libpci3 libxt6 \
    # Fonts + misc
    xvfb xauth fonts-liberation ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── 2. Python dependencies ───────────────────────────────────────────────────────
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 3. Install Playwright Chromium at BUILD time (cached layer) ──────────────────
RUN pip install --no-cache-dir playwright && \
    playwright install chromium && \
    playwright install-deps chromium

# ── 4. Download Camoufox browser at BUILD time (cached layer) ────────────────────
RUN camoufox fetch

# ── 5. Copy application source ───────────────────────────────────────────────────
COPY . .

# ── 6. Runtime: just start the bot ───────────────────────────────────────────────
CMD ["xvfb-run", "-a", "python", "Bot.py"]
