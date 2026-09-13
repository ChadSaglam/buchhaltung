FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
# NEXT_PUBLIC_* is inlined at build time: the browser must be able to reach this URL.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_BILLING_URL=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_PUBLIC_BILLING_URL=$NEXT_PUBLIC_BILLING_URL
COPY . .
RUN npm run build
CMD ["npm", "start"]
