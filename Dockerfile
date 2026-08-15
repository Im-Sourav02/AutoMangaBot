# === Stage 1: builder (installs deps & downloads browsers) ======================
FROM python:3.11-slim AS builder

WORKDIR /app

# OS packages needed by Playwright Chromium + Camoufox (Firefox)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl wget \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libxshmfence1 libx11-6 libx11-xcb1 libxcb1 libxext6 \
    libgtk-3-0 libdbus-glib-1-2 libxt6 libpci3 \
    xvfb fonts-liberation ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Playwright Chromium during BUILD
RUN pip install --no-cache-dir playwright && \
    playwright install chromium --with-deps

# Download Camoufox browser during BUILD
RUN camoufox fetch

# === Stage 2: final runtime image ===============================================
FROM python:3.11-slim AS final

WORKDIR /app

# Runtime OS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libxshmfence1 libx11-6 libx11-xcb1 libxcb1 libxext6 \
    libgtk-3-0 libdbus-glib-1-2 libxt6 libpci3 \
    xvfb fonts-liberation ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages and pre-downloaded browsers from builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache /root/.cache

# Copy application source
COPY . .
RUN chmod +x start.sh

CMD ["bash", "start.sh"]
