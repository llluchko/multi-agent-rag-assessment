FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
USER node
EXPOSE 5173
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0"]
