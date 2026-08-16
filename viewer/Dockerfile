# Peblo TV Mini — Viewer image (build with Vite, serve static with nginx).
FROM node:20-alpine AS build
WORKDIR /app

# Vite bakes VITE_* at BUILD time. The browser runs on the host, so the API
# base must be reachable from the host (http://localhost:8000). The viewer
# only ever calls the PUBLIC catalogue endpoints — no tokens are baked in.
ARG VITE_API_BASE=http://localhost:8000
ENV VITE_API_BASE=$VITE_API_BASE

COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS serve
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
