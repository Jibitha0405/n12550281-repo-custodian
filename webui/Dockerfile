FROM node:22-alpine AS web-build

WORKDIR /app
COPY webui/package.json webui/package-lock.json ./
RUN npm ci
COPY webui/ ./
RUN npm run build

FROM nginx:1.29-alpine AS webui
COPY --from=web-build /app/dist /usr/share/nginx/html
RUN printf '%s\n' \
    'server {' \
    '  listen 80;' \
    '  server_name _;' \
    '  root /usr/share/nginx/html;' \
    '  index index.html;' \
    '  location = /acp {' \
    '    proxy_pass http://127.0.0.1:7331/acp;' \
    '    proxy_http_version 1.1;' \
    '    proxy_set_header Upgrade $http_upgrade;' \
    '    proxy_set_header Connection "upgrade";' \
    '    proxy_set_header Host $host;' \
    '    proxy_read_timeout 3600s;' \
    '  }' \
    '  location = /healthz {' \
    '    access_log off;' \
    '    default_type text/plain;' \
    '    return 200 "ok\n";' \
    '  }' \
    '  location / {' \
    '    try_files $uri $uri/ /index.html;' \
    '  }' \
    '}' > /etc/nginx/conf.d/default.conf
EXPOSE 80

FROM node:22-alpine AS agent

WORKDIR /app
COPY webui/package.json webui/package-lock.json ./
RUN npm ci
COPY webui/server/ ./server/
ENV HOST=0.0.0.0
ENV PORT=7331
ENV AGENT_MODE=bedrock
EXPOSE 7331
CMD ["npm", "run", "server"]

FROM python:3.13-slim AS mcp

WORKDIR /app
COPY requirements.txt repository_context.py ./
COPY README.md ./
COPY webui/README.md ./webui/README.md
COPY CAB432-Strobe-Server-Py-1.0.0/README.md ./CAB432-Strobe-Server-Py-1.0.0/README.md
COPY CAB432-Strobe-Server-Py-1.0.0/insomnia/strobe-openapi.yaml ./CAB432-Strobe-Server-Py-1.0.0/insomnia/strobe-openapi.yaml
RUN pip install --no-cache-dir -r requirements.txt
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=3001
EXPOSE 3001
CMD ["python", "repository_context.py", "serve"]
