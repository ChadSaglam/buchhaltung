# Three stages, because the image that was here before shipped the whole source
# tree and every devDependency `npm ci` installed — typescript, eslint, vitest,
# Playwright's helpers — into production. `deps` installs, `build` compiles,
# `runtime` copies the two directories Next's standalone output actually needs.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
# NEXT_PUBLIC_* is inlined at build time: the browser must be able to reach this URL.
# These have to be set before `npm run build`, or they compile into nothing at all
# — no error, no warning, and the feature they control simply never appears.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_BILLING_URL=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_PUBLIC_BILLING_URL=$NEXT_PUBLIC_BILLING_URL
ENV NEXT_TELEMETRY_DISABLED=1
COPY . .
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
# `standalone` is a server plus the modules the build's trace reached; `static`
# is not inside it, because Next expects it to be served by a CDN when there is
# one. There is not one here, so it is copied in next to the server.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
# node:alpine ships this user; the image never runs as root.
USER node
EXPOSE 3000
# /login is public — a healthcheck that needs a session reports its own 401 as
# an outage. wget is in busybox, so this adds nothing to the image.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1:3000/login || exit 1
CMD ["node", "server.js"]
