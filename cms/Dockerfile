# Peblo TV Mini — CMS image (build with Vite, serve static with nginx).
FROM node:20-alpine AS build
WORKDIR /app

# Vite bakes VITE_* at BUILD time. The browser runs on the host, so the API
# base must be reachable from the host (http://localhost:8000), NOT the
# docker-internal hostname. Passed as build args from docker-compose.
ARG VITE_API_BASE=http://localhost:8000
ARG VITE_EDITOR_TOKEN=editor-token
ARG VITE_ADMIN_TOKEN=admin-token
ENV VITE_API_BASE=$VITE_API_BASE \
    VITE_EDITOR_TOKEN=$VITE_EDITOR_TOKEN \
    VITE_ADMIN_TOKEN=$VITE_ADMIN_TOKEN

COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS serve
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
