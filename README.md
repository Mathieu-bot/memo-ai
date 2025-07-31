# MemoAI - Memorization Assistant for Students

MemoAI is an application that helps students memorize their lessons using artificial intelligence to generate summaries, quizzes, and flashcards from their course notes.

## Features

- **Course Management**: Organize your courses and their content
- **Course Notes**: Add your notes and get AI-generated summaries
- **Quiz Generation**: Create quizzes to test your knowledge
- **Flashcards**: Generate flashcards for active recall
- **Video Upload**: Store your course videos in the cloud (Cloudinary)
- **Video Transcription**: Get transcriptions of your videos
- **Offline Mode**: Use the app even without an internet connection

## Installation

1. Clone this repository
   ```bash
   git clone https://github.com/your-username/memoai.git
   cd memoai
   ```

2. Create a virtual environment and install dependencies
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copy the .env.example file to .env and configure your environment variables
   ```bash
   cp .env.example .env
   # Edit .env file with your API key
   ```

4. Initialize the database
   ```bash
   python init_db.py
   ```

5. Start the application
   ```bash
   uvicorn app.main:app --reload
   ```

6. Access the API at http://localhost:8000

7. The API documentation is available at http://localhost:8000/docs

## Technologies Used

- **Backend**: FastAPI, SQLAlchemy
- **DataBase**: SQLite (peut être facilement remplacé par PostgreSQL)
- **Artificial intelligence**: OpenAI GPT-3.5
- **Video storage**: Cloudinary

## Project structure

```
memoai/
├── app/
│   ├── models/       # SQLAlchemy database models
│   ├── routes/       # API endpoints
│   ├── schemas/      # Pydantic schemas for validation
│   ├── services/     # Services (AI, Cloudinary, etc.)
│   └── main.py       # Main entry point
├── .env              # Environment variables
├── .env.example      # Example environment variables
├── init_db.py        # Database initialization script
└── README.md         # This file
```

## Upcoming Features

- Mobile app with offline capabilities
- User authentication system
- Sharing of quizzes and notes between students
- Learning statistics and progress tracking
- Integration with popular learning platforms

## Contributing

Contributions are welcome! Please check our contribution guide for more details.

## License

This project is licensed under the MIT License. See the LICENSE file for more information.
