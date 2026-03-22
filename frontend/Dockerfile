# ============================================================
# LEXFLOW — Frontend Dockerfile
# ============================================================
# Multi-stage build:
#   Stage 1 (builder) — npm install + vite build → /dist
#   Stage 2 (nginx)   — serve the static dist with nginx
#
# Result: ~25 MB final image (no Node.js in production).
# ============================================================

# ── Stage 1: Node build ──────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy manifests first for layer caching
COPY package.json package-lock.json ./

RUN npm ci --prefer-offline

# Copy source and build
COPY . .

# VITE_API_BASE_URL can be overridden at build time via --build-arg:
#   docker build --build-arg VITE_API_BASE_URL=https://api.mysite.com .
# Default points to the backend container exposed on port 8000.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build


# ── Stage 2: nginx static server ────────────────────────────
FROM nginx:1.27-alpine AS runtime

LABEL maintainer="LexFlow Team"
LABEL description="LexFlow frontend — React SPA served by nginx"

# Remove default nginx site config
RUN rm /etc/nginx/conf.d/default.conf

# Our custom nginx config (written below as a heredoc)
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx config that:
#   • serves the React SPA (all 404s → index.html for client-side routing)
#   • enables gzip for JS/CSS/JSON/HTML
#   • sets caching headers: long TTL for hashed assets, no-cache for index.html
#   • reverse-proxies /api → backend:8000 so the browser never sees CORS issues
COPY nginx.conf /etc/nginx/conf.d/lexflow.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
