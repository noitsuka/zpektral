FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG NEXT_PUBLIC_URL_API=http://localhost:8000
ARG NEXT_PUBLIC_URL_SITE=http://localhost:3000
ENV NEXT_PUBLIC_URL_API=$NEXT_PUBLIC_URL_API NEXT_PUBLIC_URL_SITE=$NEXT_PUBLIC_URL_SITE NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
