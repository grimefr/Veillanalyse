# 🚀 Doppelganger Tracker - Guide de Démarrage Rapide

**Temps estimé** : 5-10 minutes
**Prérequis** : Docker et Docker Compose installés

---

## ⚡ Démarrage en 3 Commandes

### Linux / macOS

```bash
# 1. Setup automatisé
chmod +x setup.sh docker-entrypoint.sh && ./setup.sh

# 2. Démarrer
docker compose up -d

# 3. Accéder au dashboard
open http://localhost:8501  # macOS
xdg-open http://localhost:8501  # Linux
```

### Windows

```cmd
REM 1. Setup automatisé
setup.bat

REM 2. Démarrer
docker compose up -d

REM 3. Accéder au dashboard
start http://localhost:8501
```

---

## 📋 Checklist de Démarrage

### Avant de Commencer

- [ ] Docker est installé et fonctionne
  ```bash
  docker --version
  docker compose version
  ```

- [ ] Vous avez au moins **4 GB de RAM disponible**
- [ ] Vous avez au moins **10 GB d'espace disque libre**

### Configuration Minimale

- [ ] Exécuter le script de setup (`setup.sh` ou `setup.bat`)
- [ ] Le fichier `.env` a été créé
- [ ] (Optionnel) Configuration Telegram API dans `.env`

### Premier Démarrage

```bash
# Construire les images
docker compose build

# Démarrer tous les services
docker compose up -d

# Vérifier que tout fonctionne
docker compose ps
```

**Attendu** :
```
NAME                        STATUS              HEALTH
doppelganger-db            Up (healthy)        healthy
doppelganger-redis         Up (healthy)        healthy
doppelganger-collector     Up                  -
doppelganger-dashboard     Up (healthy)        healthy
doppelganger-db-init       Exited (0)          -
```

---

## 🎯 Commandes Essentielles

### Avec Makefile (recommandé)

```bash
make help           # Afficher toutes les commandes
make up             # Démarrer
make down           # Arrêter
make logs           # Voir les logs
make status         # Statut des services
make restart        # Redémarrer
make clean          # Nettoyer
```

### Sans Makefile (commandes Docker)

```bash
# Démarrer
docker compose up -d

# Arrêter
docker compose down

# Voir les logs
docker compose logs -f

# Statut
docker compose ps

# Redémarrer un service
docker compose restart collector
```

---

## 🔧 Configuration de Base

### Fichier `.env` - Variables Minimales

```env
# Base de données
POSTGRES_PASSWORD=votre_mot_de_passe_securise

# Telegram (optionnel)
TELEGRAM_API_ID=votre_api_id
TELEGRAM_API_HASH=votre_api_hash
```

**Obtenir les credentials Telegram** :
1. Visiter https://my.telegram.org/apps
2. Se connecter avec votre numéro
3. Créer une application
4. Copier API ID et API Hash

### Ports Utilisés

| Service | Port | Description |
|---------|------|-------------|
| Dashboard | 8501 | Interface web Streamlit |
| PostgreSQL | 5432 | Base de données (local seulement) |
| Redis | 6379 | Cache (local seulement) |

---

## 📊 Vérification Post-Démarrage

### 1. Tous les Services sont UP

```bash
docker compose ps
```

✅ Tous les services doivent être "Up" ou "Exited (0)" pour db-init

### 2. Les Healthchecks Passent

```bash
docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Health}}"
```

✅ PostgreSQL, Redis et Dashboard doivent être "healthy"

### 3. Base de Données Initialisée

```bash
docker compose exec postgres psql -U doppelganger -d doppelganger -c "\dt"
```

✅ Vous devez voir 10 tables listées

### 4. Dashboard Accessible

```bash
curl http://localhost:8501/_stcore/health
```

✅ Doit retourner HTTP 200

Ou ouvrir dans le navigateur : http://localhost:8501

### 5. Logs Sans Erreur

```bash
docker compose logs collector | grep -i error
```

✅ Aucune erreur critique (quelques warnings sont normaux)

---

## 🎮 Utilisation Basique

### Collecter des Données

```bash
# Collection automatique (en continu)
# Le service collector tourne en permanence

# Collection manuelle
docker compose exec collector python main.py collect --limit 50
```

### Analyser les Données

```bash
# Analyse complète (one-shot)
docker compose run --rm analyzer

# Analyse NLP seulement
docker compose run --rm analyzer analyze --nlp-only --limit 100

# Analyse réseau seulement
docker compose run --rm analyzer analyze --network-only --days 7
```

### Consulter le Dashboard

1. Ouvrir http://localhost:8501
2. Explorer les statistiques
3. Voir les graphiques de propagation
4. Consulter les alertes de propagande

---

## 🐛 Dépannage Rapide

### Problème : Container ne démarre pas

```bash
# Voir les logs détaillés
docker compose logs <nom_du_service>

# Redémarrer le service
docker compose restart <nom_du_service>

# Rebuild complet
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Problème : "Port already in use"

**Solution 1** : Changer le port dans `.env`
```env
DASHBOARD_PORT=8502
```

**Solution 2** : Arrêter le processus utilisant le port
```bash
# Linux/macOS
lsof -i :8501
kill -9 <PID>

# Windows
netstat -ano | findstr :8501
taskkill /PID <PID> /F
```

### Problème : Database connection failed

```bash
# Vérifier que postgres est healthy
docker compose ps postgres

# Attendre 10 secondes et réessayer
sleep 10
docker compose restart collector

# Vérifier les credentials
cat .env | grep POSTGRES
```

### Problème : Out of memory

**Solution** : Augmenter la mémoire Docker

- Docker Desktop → Settings → Resources → Memory
- Passer à 6-8 GB minimum

**Alternative** : Réduire les batch sizes dans `.env`
```env
NLP_BATCH_SIZE=100  # au lieu de 500
```

---

## 📚 Documentation Complète

| Document | Contenu |
|----------|---------|
| `README-DOCKER.md` | Guide complet Docker (EN) |
| `RESUME-AMELIORATIONS-FR.md` | Résumé des améliorations (FR) |
| `VALIDATION-CHECKLIST.md` | Checklist de validation (EN) |
| `DOCKER-IMPROVEMENTS.md` | Détails techniques (EN) |
| `.env.example` | Variables d'environnement documentées |

### Commandes de Documentation

```bash
# Voir toutes les commandes make
make help

# Voir les infos système
make info

# Ouvrir la doc Docker
make doc
```

---

## 🔄 Workflow Quotidien

### Matin (démarrage)

```bash
docker compose up -d
docker compose logs -f --tail=50
```

### Pendant la journée (monitoring)

```bash
# Vérifier le statut
make status

# Voir les derniers logs
make logs

# Voir l'utilisation ressources
make stats
```

### Soir (arrêt)

```bash
# Arrêter proprement
docker compose down

# OU garder en arrière-plan
# (les services continuent de tourner)
```

### Hebdomadaire (maintenance)

```bash
# Sauvegarder la base de données
make db-backup

# Nettoyer les ressources inutilisées
make clean

# Vérifier les mises à jour
git pull
make rebuild
```

---

## 🎯 Prochaines Étapes

Une fois le système fonctionnel :

1. **Configurer les sources** : Éditer `config/sources.yaml`
2. **Personnaliser les narratives** : Éditer `config/keywords.yaml`
3. **Ajuster les paramètres** : Modifier `.env` selon vos besoins
4. **Planifier des analyses** : Configurer un cron pour l'analyzer
5. **Explorer le dashboard** : Familiarisez-vous avec les visualisations

---

## 💡 Astuces

### Accès Shell dans un Container

```bash
# Collector
docker compose exec collector bash

# Dashboard
docker compose exec dashboard bash

# PostgreSQL
docker compose exec postgres psql -U doppelganger
```

### Voir les Données Collectées

```bash
# Nombre de contenus
docker compose exec postgres psql -U doppelganger -d doppelganger -c "SELECT COUNT(*) FROM content;"

# Derniers contenus
docker compose exec postgres psql -U doppelganger -d doppelganger -c "SELECT title, published_at FROM content ORDER BY published_at DESC LIMIT 10;"
```

### Export des Données

```bash
# Les exports sont dans ./exports/
ls -lh exports/

# Graphes réseau
ls exports/graphs/*.gexf

# Rapports
ls exports/reports/*.csv
```

---

## 🆘 Aide Supplémentaire

### Réinitialisation Complète

**⚠️ ATTENTION : Supprime toutes les données**

```bash
# Arrêter et supprimer tout
docker compose down -v

# Nettoyer Docker
docker system prune -a -f

# Recommencer from scratch
./setup.sh
docker compose build
docker compose up -d
```

### Support

- **Documentation** : Lire `README-DOCKER.md`
- **Problèmes connus** : Consulter la section Troubleshooting
- **Logs** : `docker compose logs -f`
- **Validation** : Utiliser `VALIDATION-CHECKLIST.md`

---

## ✅ Checklist de Succès

Votre installation est réussie si :

- [ ] `docker compose ps` montre tous les services UP
- [ ] Dashboard accessible sur http://localhost:8501
- [ ] Aucune erreur dans `docker compose logs`
- [ ] Base de données contient 10 tables
- [ ] Service collector tourne sans crash
- [ ] Vous pouvez lancer une analyse

---

**Félicitations ! Votre Doppelganger Tracker est opérationnel ! 🎉**

Pour approfondir, consultez `README-DOCKER.md` et `RESUME-AMELIORATIONS-FR.md`.
