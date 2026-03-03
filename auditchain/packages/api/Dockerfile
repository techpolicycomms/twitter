FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

RUN npx prisma generate --schema=src/models/schema.prisma
RUN npm run build

EXPOSE 3001

CMD ["sh", "-c", "npx prisma migrate deploy --schema=src/models/schema.prisma && node dist/index.js"]
