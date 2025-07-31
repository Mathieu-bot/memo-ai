# MemoAI - Aide à la mémorisation pour étudiants

MemoAI est une application qui aide les étudiants à mémoriser leurs cours en utilisant l'intelligence artificielle pour générer des résumés, des quiz et des flashcards à partir de leurs notes de cours.

## Fonctionnalités

- **Gestion des cours**: Organisez vos cours et leurs contenus
- **Notes de cours**: Ajoutez vos notes et obtenez des résumés générés par IA
- **Génération de quiz**: Créez des quiz pour tester vos connaissances
- **Flashcards**: Générez des flashcards pour la mémorisation active
- **Upload de vidéos**: Stockez vos vidéos de cours dans le cloud (Cloudinary)
- **Transcription de vidéos**: Obtenez des transcriptions de vos vidéos
- **Mode hors ligne**: Utilisez l'application même sans connexion internet

## Installation

1. Clonez ce dépôt
   ```bash
   git clone https://github.com/votre-username/memoai.git
   cd memoai
   ```

2. Créez un environnement virtuel et installez les dépendances
   ```bash
   python -m venv venv
   source venv/bin/activate  # Sur Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copiez le fichier .env.example en .env et configurez vos variables d'environnement
   ```bash
   cp .env.example .env
   # Modifiez le fichier .env avec vos propres clés API
   ```

4. Initialisez la base de données
   ```bash
   python init_db.py
   ```

5. Lancez l'application
   ```bash
   uvicorn app.main:app --reload
   ```

6. Accédez à l'API à l'adresse http://localhost:8000

7. La documentation de l'API est disponible à http://localhost:8000/docs

## Technologies utilisées

- **Backend**: FastAPI, SQLAlchemy
- **Base de données**: SQLite (peut être facilement remplacé par PostgreSQL)
- **Intelligence artificielle**: OpenAI GPT-3.5
- **Stockage de vidéos**: Cloudinary

## Structure du projet

```
memoai/
├── app/
│   ├── models/       # Modèles de base de données SQLAlchemy
│   ├── routes/       # Points d'entrée de l'API
│   ├── schemas/      # Schémas Pydantic pour la validation
│   ├── services/     # Services (IA, Cloudinary, etc.)
│   └── main.py       # Point d'entrée principal
├── .env              # Variables d'environnement
├── .env.example      # Exemple de variables d'environnement
├── init_db.py        # Script d'initialisation de la base de données
└── README.md         # Ce fichier
```

## Fonctionnalités à venir

- Application mobile avec fonctionnalités hors ligne
- Système d'authentification des utilisateurs
- Partage de quiz et de notes entre étudiants
- Statistiques d'apprentissage et suivi des progrès
- Intégration avec des plateformes d'apprentissage populaires

## Contribution

Les contributions sont les bienvenues ! Veuillez consulter notre guide de contribution pour plus de détails.

## Licence

Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails.
