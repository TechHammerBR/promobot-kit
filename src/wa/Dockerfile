FROM node:22-alpine
WORKDIR /app
COPY package.json ./
RUN apk add --no-cache git && npm install --omit=dev && npm cache clean --force
COPY index.mjs ./
CMD ["node", "index.mjs"]
