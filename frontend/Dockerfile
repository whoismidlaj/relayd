# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Install native dependencies required by some node modules in Alpine
RUN apk add --no-cache libc6-compat python3 make g++

COPY package*.json ./
COPY yarn.lock ./
# Use increased network timeout to prevent Coolify build failures
RUN yarn install --network-timeout 1000000

COPY . .
RUN yarn build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/build /usr/share/nginx/html

# Add nginx config for React Router
RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html index.htm; \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
