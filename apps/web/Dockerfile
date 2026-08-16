# apps/web Dockerfile -- two-stage build: a Node build stage producing the
# Vite static output (`npm run build` = `tsc --noEmit && vite build`,
# apps/web/package.json), then a minimal static-file server stage. Follows
# docs/operations/container-conventions.md: non-root, minimal base image,
# no secrets baked in (this is a static SPA bundle -- it has no
# server-side config to bake in), read-only-root-filesystem compatible
# (the serve stage's own runtime writable paths are explicit tmpfs mounts
# in docker-compose.local.yml, not a writable image).

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# nginxinc/nginx-unprivileged (not the stock `nginx` image) specifically
# because it already creates and runs as an unprivileged, non-root user
# and listens on 8080 by default -- rule 1 (non-root) needs no extra
# USER/port juggling on top of it.
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
