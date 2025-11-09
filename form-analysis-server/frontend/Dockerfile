# Frontend Dockerfile for React + Vite Application
FROM node:20-alpine as base

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production --silent && npm cache clean --force

# Development stage
FROM base as development

# Install curl for health checks
RUN apk add --no-cache curl

# Install all dependencies (including dev)
RUN npm ci --silent

# Copy source code
COPY . .

# Expose port
EXPOSE 5173

# Set environment variables for development
ENV NODE_ENV=development
ENV VITE_API_URL=http://localhost:8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:5173 || exit 1

# Start development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Production build stage
FROM base as build

# Install all dependencies
RUN npm ci --silent

# Copy source code
COPY . .

# Build for production
RUN npm run build

# Production stage
FROM nginx:alpine as production

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built app from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Add health check script
RUN echo '#!/bin/sh' > /usr/local/bin/health-check.sh && \
    echo 'curl -f http://localhost:80/ || exit 1' >> /usr/local/bin/health-check.sh && \
    chmod +x /usr/local/bin/health-check.sh

# Install curl for health checks
RUN apk add --no-cache curl

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD /usr/local/bin/health-check.sh

# Start nginx
CMD ["nginx", "-g", "daemon off;"]