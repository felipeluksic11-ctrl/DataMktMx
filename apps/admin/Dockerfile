FROM node:20-alpine AS base

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Create public dir if missing
RUN mkdir -p public

ARG NEXT_PUBLIC_API_URL=http://localhost:3001/api/v1
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:20-alpine AS production

WORKDIR /app

COPY --from=base /app/.next/standalone ./
COPY --from=base /app/.next/static ./.next/static
COPY --from=base /app/public ./public

EXPOSE 3000

ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
