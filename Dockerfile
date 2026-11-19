FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RECEIPTSIFT_DATA_DIR=/app/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY index.html seo.html login.html register.html forgot-password.html reset-password.html account.html admin.html pricing.html batches.html privacy.html terms.html cookies.html refunds.html styles.css app-shell.css seo.css auth.css admin.css admin-diagnostics.css pricing.css batch-workspace.css legal.css locale.css app.js seo.js login.js register.js forgot-password.js reset-password.js account.js admin.js analytics.js pricing.js batch-workspace.js locale.js robots.txt ./
COPY content ./content
COPY content.css ./
COPY scripts ./scripts
COPY docker-entrypoint.sh /usr/local/bin/receiptsift-entrypoint

RUN useradd --create-home --uid 10001 receiptsift \
    && mkdir -p /app/data \
    && chown -R receiptsift:receiptsift /app \
    && chmod +x /usr/local/bin/receiptsift-entrypoint

EXPOSE 4317

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '4317') + '/api/health', timeout=3)"

ENTRYPOINT ["receiptsift-entrypoint"]
CMD ["sh", "-c", "python -m uvicorn backend.server:app --host 0.0.0.0 --port ${PORT:-4317}"]
