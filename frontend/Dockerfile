# Build stage
FROM node:20-slim AS builder

WORKDIR /app

# Install native dependencies just in case
RUN apt-get update && apt-get install -y python3 make g++ && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
COPY yarn.lock ./
# Use increased network timeout
RUN yarn install --network-timeout 1000000

COPY . .
RUN yarn build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/build /usr/share/nginx/html

# Add nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
