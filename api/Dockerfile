FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci --production=false

COPY . .
RUN npx prisma generate

ENV DATABASE_URL=postgresql://dummy:dummy@localhost:5432/dummy
RUN npm run build

EXPOSE 3001

CMD ["node", "dist/main"]
