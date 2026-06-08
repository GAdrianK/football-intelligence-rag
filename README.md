# ⚽ Football IQ Assistant — MVP V1

> Assistant tactique football à intelligence artificielle, propulsé par un moteur RAG local (Retrieval-Augmented Generation).

---

## 🎯 Présentation

**Football IQ Assistant** est un assistant conversationnel spécialisé dans l'analyse tactique du football.  
Il répond à des questions en s'appuyant exclusivement sur une base de connaissances structurée de **24 documents tactiques** (268 chunks indexés), couvrant formations, pressing, transitions, rôles et phases offensives.

Trois modes de réponse adaptés à chaque profil :
- 🎓 **Coach** — consignes terrain, séances d'entraînement structurées
- 🔍 **Analyste** — observations tactiques cliniques, forces/faiblesses
- 📣 **Fan** — vulgarisation accessible et vivante

---

## ✨ Fonctionnalités MVP

| Fonctionnalité | Statut |
|---|---|
| Chat conversationnel multi-mode | ✅ |
| RAG local TF-IDF (268 chunks, 24 documents) | ✅ |
| Classification des requêtes (salutation, hors-sujet, tactique) | ✅ |
| Scoring hybride intention défensive/offensive | ✅ |
| Persistence localStorage (restauration au rechargement) | ✅ |
| Bouton Copier (feedback visuel) | ✅ |
| Bouton Simplifier (reformulation débutant) | ✅ |
| Bouton Approfondir (détails tactiques enrichis) | ✅ |
| Export PDF tactique (téléchargement direct) | ✅ |
| Réinitialisation de session | ✅ |
| Interface responsive dark mode | ✅ |
| Mode OpenAI (GPT-4o-mini) si clé API présente | ✅ |
| Fallback offline TF-IDF sans clé API | ✅ |

---

## 🏗️ Architecture

```
IA FOOT/
├── backend/              # API FastAPI
│   ├── app/
│   │   ├── api/          # Routes (chat, search, pdf, health)
│   │   ├── services/     # RAGEngine, ChatService, QueryClassifier, PDFGenerator
│   │   ├── schemas/      # Modèles Pydantic
│   │   └── prompts/      # Prompts système Coach / Analyste / Fan
│   └── tests/            # 18 tests unitaires et d'intégration
├── frontend/             # Interface SPA Vanilla JS
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── football-rag-system/  # Base de connaissances Markdown
    └── data_football/knowledge_base/   # 24 fichiers tactiques
```

---

## 🚀 Installation

### Prérequis
- Python 3.10+
- Un navigateur web moderne

### 1. Cloner et configurer

```bash
cd "IA FOOT/backend"
python -m venv venv
venv/bin/pip install -r requirements.txt
```

### 2. Configurer l'environnement

```bash
cp .env.example .env
# Éditer .env si vous avez une clé OpenAI
```

---

## ▶️ Lancer l'application

### Backend (Terminal 1)

```bash
cd "IA FOOT/backend"
venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Logs attendus :
```
Indexation locale réussie de 268 chunks via TF-IDF.
Football IQ Assistant API démarrée avec succès.
```

### Frontend (Navigateur)

Ouvrir directement dans le navigateur :
```
file:///chemin/vers/IA FOOT/frontend/index.html
```

Le badge vert en haut confirme la connexion au backend.

---

## 🔌 API — Endpoints principaux

### Health check
```bash
curl http://127.0.0.1:8000/api/health
```

### Chat
```bash
curl -X POST "http://127.0.0.1:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Explique-moi le faux 9", "mode": "analyst"}'
```

### Recherche RAG
```bash
curl "http://127.0.0.1:8000/api/search?q=pressing+haut&top_k=3"
```

### Export PDF
```bash
curl -X POST "http://127.0.0.1:8000/api/export-pdf" \
  -H "Content-Type: application/json" \
  -d '{"title":"Séance pressing","blocks":[{"title":"Exercice 1","content":"Rondo 4v2."}]}' \
  -o fiche.pdf
```

---

## 💬 Exemples de requêtes

| Mode | Question exemple |
|---|---|
| Coach | "Prépare une séance de pressing haut pour U17" |
| Analyste | "Quels sont les avantages et faiblesses du 3-5-2 ?" |
| Fan | "C'est quoi un faux 9 en vrai ?" |
| Coach | "Comment défendre en bloc bas face à une équipe qui joue long ?" |
| Analyste | "Explique la différence entre un pivot et un double pivot" |

---

## ⚠️ Limites actuelles

Voir [`docs/known_limitations.md`](docs/known_limitations.md) pour le détail complet.

- Mode offline : réponses basées sur extraction directe du RAG (sans LLM complet)
- Base de connaissances textuelle uniquement — pas de vidéo ni de schémas
- Pas d'authentification ni de multi-utilisateur
- Pas de mémoire long-terme entre sessions (localStorage limité à la session courante)

---

## 🧪 Tests

```bash
cd backend
venv/bin/pytest tests/ -v
# → 18 passed
```

---

## 🗺️ Roadmap

| Priorité | Fonctionnalité |
|---|---|
| 🔴 Court terme | Connexion OpenAI GPT-4o-mini pour réponses enrichies |
| 🔴 Court terme | Déploiement sur Render / Railway avec CORS configuré |
| 🟡 Moyen terme | Interface d'upload de documents tactiques personnalisés |
| 🟡 Moyen terme | Historique multi-sessions avec IndexedDB |
| 🟢 Long terme | Intégration de schémas tactiques SVG interactifs |
| 🟢 Long terme | Module d'analyse vidéo avec extraction de données |

---

## 📄 Licence

Projet personnel — usage pédagogique et démonstration.
