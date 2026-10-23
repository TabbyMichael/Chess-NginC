# Chess Engine Web — production image (REL-001).
# Stage 1: build the static bundle.
FROM node:20-alpine AS build
WORKDIR /srv/web
# Google Sign-In client ID baked into the bundle; empty hides the button.
ARG VITE_GOOGLE_CLIENT_ID=
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
COPY package.json package-lock.json ./
RUN npm ci
COPY . ./
RUN npm run build

# Stage 2: serve over HTTP. TLS terminates at the reverse proxy (REL-003).
FROM nginx:alpine AS runtime
COPY --from=build /srv/web/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
