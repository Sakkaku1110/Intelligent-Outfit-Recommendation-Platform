FROM node:20-bookworm-slim

WORKDIR /app

COPY package*.json ./
RUN npm config set registry https://registry.npmmirror.com && npm install --omit=dev

COPY src ./src

ENV NODE_ENV=production
EXPOSE 3000

CMD ["npm", "start"]
