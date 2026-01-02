# 🐳 Guide Docker - Doppelganger Tracker v2

**Version 4.0** | **Production Ready**

---

## 🎯 Vue d'Ensemble

Système Docker optimisé avec :
- ✅ Build 70% plus rapide (10min → 3min)
- ✅ Image 68% plus petite (2.5GB → 800MB)
- ✅ Multi-stage build
- ✅ Health checks automatiques
- ✅ Initialisation DB automatique

---

## 🚀 Démarrage Rapide

```bash
# Setup automatique
./setup.sh  # Linux/macOS
setup.bat   # Windows

# Démarrer
docker compose up -d

# Vérifier
docker compose ps
open http://localhost:8501
```

---

## 📦 Services

| Service | Port | Description | Health Check |
|---------|------|-------------|--------------|
| **postgres** | 5432 | PostgreSQL 15 | `pg_isready` |
| **redis** | 6379 | Cache Redis | `redis-cli ping` |
| **collector** | - | Collection background | - |
| **analyzer** | - | Analyse one-shot | - |
| **dashboard** | 8501 | Interface Streamlit | HTTP 200 |
| **db-init** | - | Init DB (exit 0) | - |

---

## ⚙️ Configuration

### Fichier `.env` (Minimal)

```env
# Base de données (REQUIS)
POSTGRES_PASSWORD=votre_mot_de_passe_securise

# Telegram (Optionnel)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef...
```

### Variables Complètes

Voir [`.env.example`](../.env.example) pour toutes les options.

---

## 🔧 Commandes

### Makefile (Recommandé)

```bash
make help       # Liste commandes
make up         # Démarrer
make down       # Arrêter
make logs       # Logs temps réel
make status     # Statut services
make restart    # Redémarrer
make db-backup  # Backup DB
make clean      # Nettoyer
```

### Docker Compose Direct

```bash
# Gestion services
docker compose up -d
docker compose down
docker compose restart <service>
docker compose ps

# Logs
docker compose logs -f
docker compose logs -f collector
docker compose logs --tail=100 dashboard

# Shell
docker compose exec collector bash
docker compose exec postgres psql -U doppelganger

# Rebuild
docker compose build --no-cache
docker compose up -d --force-recreate
```

---

## 🗄️ Base de Données

### Connexion

```bash
# Via Docker
docker compose exec postgres psql -U doppelganger

# SQL direct
docker compose exec postgres psql -U doppelganger -d doppelganger -c "SELECT COUNT(*) FROM content;"
```

### Backup & Restore

```bash
# Backup
make db-backup
# OU
docker compose exec postgres pg_dump -U doppelganger doppelganger > backup.sql

# Restore
docker compose exec -T postgres psql -U doppelganger doppelganger < backup.sql
```

### Migrations

```bash
# Appliquer migration
docker compose exec postgres psql -U doppelganger -d doppelganger \
    -f /docker-entrypoint-initdb.d/add_indexes_and_constraints.sql
```

Voir [migrations/README.md](../migrations/README.md) pour détails.

---

## 📊 Monitoring

### Health Checks

```bash
# Statut complet
docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Health}}"

# Dashboard health
curl http://localhost:8501/_stcore/health
```

### Ressources

```bash
# Utilisation en temps réel
docker stats

# Espace disque
docker system df
```

### Logs

```bash
# Tous les services
docker compose logs -f

# Service spécifique
docker compose logs -f collector

# Depuis une date
docker compose logs --since 2026-01-02T10:00:00

# Chercher erreurs
docker compose logs | grep -i error
```

---

## 🔧 Troubleshooting

### Container ne démarre pas

```bash
# Logs détaillés
docker compose logs <service>

# Redémarrer
docker compose restart <service>

# Rebuild complet
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Port déjà utilisé (8501)

```bash
# Option 1: Changer port
echo "DASHBOARD_PORT=8502" >> .env
docker compose up -d

# Option 2: Tuer processus
lsof -i :8501  # Trouver PID
kill -9 <PID>
```

### Base de données inaccessible

```bash
# Vérifier santé
docker compose exec postgres pg_isready

# Attendre et redémarrer
sleep 10
docker compose restart collector
```

### Out of Memory

```bash
# Augmenter RAM Docker Desktop
# Settings → Resources → Memory → 6-8 GB

# OU réduire batch sizes
echo "NLP_BATCH_SIZE=100" >> .env
docker compose restart collector
```

### Réinitialisation Complète

```bash
# ⚠️ ATTENTION: Supprime toutes les données!
docker compose down -v
docker system prune -a -f
./setup.sh
docker compose up -d
```

---

## 🏗️ Architecture Docker

### Multi-Stage Build

```dockerfile
# Stage 1: Builder
FROM python:3.11.7-slim AS builder
RUN pip install --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11.7-slim AS runtime
COPY --from=builder /root/.local /root/.local
ENTRYPOINT ["docker-entrypoint.sh"]
```

**Bénéfices** : -68% taille image

### .dockerignore

Réduit le build context de 90% :

```
__pycache__/
*.pyc
venv/
data/
logs/
.git/
*.md
```

### Entrypoint Intelligent

`docker-entrypoint.sh` gère :
- Wait-for-database
- Initialisation automatique
- Routing de commandes

---

## 🔒 Sécurité

### Containers Non-Root

```dockerfile
RUN useradd -m -u 1000 appuser
USER appuser
```

### Volumes Read-Only

```yaml
volumes:
  - ./config:/app/config:ro  # Read-only
```

### Network Isolation

Seul le dashboard (8501) est exposé. PostgreSQL et Redis sont internes.

### Secrets (Production)

**Recommandé** : Utiliser Docker secrets au lieu de variables d'environnement.

```yaml
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt

services:
  postgres:
    secrets:
      - postgres_password
```

---

## 📈 Performance

### Build Optimisations

| Optimisation | Gain |
|--------------|------|
| .dockerignore | -90% context |
| Multi-stage build | -68% image |
| Layer caching | -70% rebuild time |

### Runtime Optimisations

- **Connection pooling** : 50 connexions max
- **Health checks** : Redémarrage automatique
- **Resource limits** : CPU/Memory caps

---

## 🔄 Workflow

### Développement

```bash
# Démarrer
docker compose up -d

# Logs en temps réel
docker compose logs -f collector

# Tests
docker compose exec collector pytest

# Arrêter
docker compose down
```

### Production

```bash
# Build images
docker compose build

# Démarrer en détaché
docker compose up -d

# Monitoring
docker compose ps
docker stats

# Logs
docker compose logs --since 1h

# Backup quotidien (cron)
0 2 * * * cd /path/to/project && make db-backup
```

---

## 📚 Références

- **Setup** : [QUICKSTART.md](../QUICKSTART.md)
- **Commandes** : [REFERENCE.md](../REFERENCE.md)
- **Migrations** : [migrations/README.md](../migrations/README.md)
- **Validation** : [VALIDATION-CHECKLIST.md](../VALIDATION-CHECKLIST.md)

---

**Dernière mise à jour** : 2026-01-02
**Build time** : 3 min · **Image size** : 800 MB · **Statut** : ✅ Production Ready
