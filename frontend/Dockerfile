# Chhatri frontend (SPEC §20, §23)
# Multi-stage: Node build → nginx SPA + proxy

# Stage 1: Build
FROM node:22-alpine as builder

WORKDIR /app

# Copy package files
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY frontend/src ./src
COPY frontend/public ./public
COPY frontend/index.html ./
COPY frontend/vite.config.ts ./
COPY frontend/tsconfig.json ./
COPY frontend/tsconfig.app.json ./
COPY frontend/tsconfig.node.json ./
COPY frontend/tailwind.config.js ./
COPY frontend/postcss.config.js ./

# Build
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

# Copy config
COPY frontend/nginx.conf /etc/nginx/nginx.conf

# Copy built app
COPY --from=builder /app/dist /usr/share/nginx/html

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80 || exit 1

# Expose
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
