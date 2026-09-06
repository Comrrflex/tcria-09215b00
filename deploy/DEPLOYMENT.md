# TCRIA - Digital Ocean Deployment Runbook

**Objetivo:** Deploy do TCRIA em Digital Ocean (Droplet) de forma simples e manutenível.

**Tempo estimado:** 30 minutos  
**Pré-requisitos:** SSH access ao droplet, Docker + Docker Compose instalados

---

## 1. Setup Inicial do Droplet

### 1.1 SSH no seu droplet
```bash
ssh root@your-droplet-ip
```

### 1.2 Atualizar sistema
```bash
apt-get update && apt-get upgrade -y
apt-get install -y curl wget git
```

### 1.3 Instalar Docker
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Add your user to docker group (if not root)
usermod -aG docker $USER
newgrp docker
```

### 1.4 Instalar Docker Compose
```bash
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
docker-compose --version
```

---

## 2. Clonar e Preparar o Repositório

### 2.1 Clone do repo
```bash
cd /opt
git clone https://github.com/Comrrflex/tcria-09215b00.git
cd tcria-09215b00
```

### 2.2 Criar arquivo `.env` com segredos
```bash
cp .env.production .env
nano .env  # Edit com seus valores reais
```

**Gerar secrets seguros:**
```bash
# JWT Secret
openssl rand -hex 32

# Signing Secret
openssl rand -hex 32
```

### 2.3 Criar diretórios de persistência
```bash
mkdir -p output cases
chmod 755 output cases
```

---

## 3. Build e Deploy

### 3.1 Build da imagem Docker
```bash
docker-compose build
```

### 3.2 Iniciar container
```bash
docker-compose up -d
```

### 3.3 Verificar status
```bash
docker-compose ps
docker-compose logs -f tcria
```

**Esperado:** Container rodando na porta 8000

### 3.4 Teste de healthcheck
```bash
curl -X GET http://localhost:8000/health
```

**Resposta esperada:**
```json
{"status": "ok"}
```

---

## 4. Setup de Reverse Proxy (Nginx)

### 4.1 Instalar Nginx
```bash
apt-get install -y nginx
```

### 4.2 Criar config do Nginx
```bash
cat > /etc/nginx/sites-available/tcria.conf << 'EOF'
upstream tcria {
    server localhost:8000;
}

server {
    listen 80;
    server_name tcria.your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tcria.your-domain.com;

    # SSL certificates (will setup with certbot)
    ssl_certificate /etc/letsencrypt/live/tcria.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tcria.your-domain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://tcria;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts for long-running audits
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint (no auth required)
    location /health {
        proxy_pass http://tcria;
        access_log off;
    }
}
EOF
```

### 4.3 Habilitar site
```bash
ln -s /etc/nginx/sites-available/tcria.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
```

### 4.4 Setup SSL com Certbot
```bash
apt-get install -y certbot python3-certbot-nginx
certbot certonly --nginx -d tcria.your-domain.com
```

---

## 5. Monitoramento & Manutenção

### 5.1 Ver logs
```bash
# Real-time logs
docker-compose logs -f tcria

# Últimas 100 linhas
docker-compose logs --tail 100 tcria

# Logs com timestamp
docker-compose logs --timestamps tcria
```

### 5.2 Restart do container
```bash
docker-compose restart tcria
```

### 5.3 Parar o container
```bash
docker-compose down
```

### 5.4 Atualizar código
```bash
cd /opt/tcria-09215b00
git pull origin main
docker-compose build
docker-compose up -d
```

### 5.5 Verificar recursos
```bash
docker stats
docker ps --format "{{.Names}}\t{{.Status}}\t{{.Ports}}"
```

---

## 6. Backup & Persistência

### 6.1 Backup de audit outputs
```bash
# Manual backup
tar -czf tcria-output-$(date +%Y%m%d-%H%M%S).tar.gz output/

# Backup automático (cron)
# Add to crontab -e:
0 2 * * * cd /opt/tcria-09215b00 && tar -czf /backup/tcria-output-$(date +\%Y\%m\%d).tar.gz output/
```

### 6.2 Persistência de dados
Os volumes estão configurados em `docker-compose.yml`:
- `output/` → Audit results (critical)
- `cases/` → Case data (if used)

---

## 7. Troubleshooting

### Container não inicia
```bash
docker-compose logs tcria
# Procure por:
# - Missing environment variables
# - Port already in use
# - Image build errors
```

### Port 8000 já em uso
```bash
lsof -i :8000
kill -9 <PID>
```

### SSL certificate error
```bash
# Renew certificate
certbot renew --force-renewal

# Check certificate expiry
certbot certificates
```

### Memory/CPU issues
```bash
# Limit resources (edit docker-compose.yml)
# Add under 'tcria' service:
# deploy:
#   resources:
#     limits:
#       cpus: '1'
#       memory: 1G
```

---

## 8. Segurança Checklist

- [ ] Alterar secrets em `.env` (não usar defaults)
- [ ] Setup SSL/TLS com Certbot
- [ ] Configure firewall (ufw)
- [ ] Habilitar SSH key-only login
- [ ] Configurar backups automáticos
- [ ] Setup monitoring (opcional: Datadog, Prometheus)
- [ ] Criar script de atualização automática

### Firewall básico (ufw)
```bash
ufw enable
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw status
```

---

## 9. Update & Rollback

### Atualizar para nova versão
```bash
cd /opt/tcria-09215b00
git fetch origin
git checkout main
git pull
docker-compose build
docker-compose up -d
```

### Rollback (se der problema)
```bash
git revert HEAD --no-edit
docker-compose build
docker-compose up -d
```

---

## 10. Contatos & Suporte

- Repo: https://github.com/Comrrflex/tcria-09215b00
- Issues: GitHub Issues
- Documentation: README.md

---

**Última atualização:** 2026-09-06  
**Status:** Production-ready
