# Chhatri console image (SPEC §20, §23; binding decision B7).
#
# Build context is frontend/ (see frontend/.dockerignore). Stage 1 runs the B7 `build` script
# (tsc -b && vite build); stage 2 serves dist/ with unprivileged nginx on :8080 and proxies /api and
# /webhooks to the backend. frontend/nginx.conf is an nginx *template*: the image renders
# ${CHHATRI_BACKEND_UPSTREAM} (default backend:8000, the compose service) at container start.
FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.30-alpine

ENV CHHATRI_BACKEND_UPSTREAM=backend:8000

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "--quiet", "--output-document=/dev/null", "http://127.0.0.1:8080/healthz"]
