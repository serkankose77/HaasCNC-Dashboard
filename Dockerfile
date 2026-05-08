FROM python:3.12-alpine

WORKDIR /app

# Stdlib only — no requirements.txt needed.
COPY server.py dashboard.html machines.example.json ./

# Run as non-root.
RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app
USER app

EXPOSE 8000

# machines.json is mounted as a volume at runtime (./machines.json -> /app/machines.json:ro).
# Real shop-floor IPs never enter the image; the same image deploys to any server.

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://localhost:8000/api/machines || exit 1

CMD ["python3", "-u", "server.py"]
