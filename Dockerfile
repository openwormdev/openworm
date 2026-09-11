FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless build-essential && apt-get clean
WORKDIR /app
COPY requirements.lock pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps .
COPY web ./web
RUN useradd --system --create-home worker
USER worker
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV WORM_WEB_ROOT=/app/web
ENV WORM_REMOTE_MODE=1
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "wormbrain.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
