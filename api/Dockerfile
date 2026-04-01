FROM node:20-slim AS build

RUN apt-get update && apt-get install -y openssl libssl-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npx prisma generate
RUN npm run build

FROM node:20-slim

RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./
COPY --from=build /app/prisma ./prisma

EXPOSE 3001

COPY --from=build /app/node_modules/.prisma ./node_modules/.prisma

CMD ["sh", "-c", "npx prisma db push --skip-generate && node dist/main"]
