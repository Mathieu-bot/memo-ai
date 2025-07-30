import openai
import os
from typing import List, Dict, Any

openai.api_key = os.getenv("OPENAI_API_KEY")

class AIService:
    @staticmethod
    def generate_quiz(course_title: str, course_description: str, num_questions: int = 5) -> Dict[str, Any]:
        """Génère un quiz basé sur le cours fourni."""
        prompt = f"""Génère un quiz de {num_questions} questions sur le sujet: {course_title}.

Description du cours: {course_description}

Pour chaque question, génère 4 réponses possibles dont une seule est correcte.
        Format de retour:
        {{
          'title': 'Titre du quiz',
          'description': 'Description du quiz',
          'questions': [
            {{
              'text': 'Texte de la question',
              'explanation': 'Explication de la réponse correcte',
              'answers': [
                {{'text': 'Réponse 1', 'is_correct': true}},
                {{'text': 'Réponse 2', 'is_correct': false}},
                {{'text': 'Réponse 3', 'is_correct': false}},
                {{'text': 'Réponse 4', 'is_correct': false}}
              ]
            }},
            ...
          ]
        }}
        """

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Tu es un assistant qui génère des quiz éducatifs."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.7
        )

        try:
            return eval(response.choices[0].message.content)
        except:
            # En cas d'erreur de format, retourner un quiz par défaut
            return {
                "title": f"Quiz sur {course_title}",
                "description": f"Questions générées sur {course_title}",
                "questions": [
                    {
                        "text": "Question exemple",
                        "explanation": "Ceci est une explication exemple",
                        "answers": [
                            {"text": "Réponse correcte", "is_correct": True},
                            {"text": "Réponse incorrecte 1", "is_correct": False},
                            {"text": "Réponse incorrecte 2", "is_correct": False},
                            {"text": "Réponse incorrecte 3", "is_correct": False}
                        ]
                    }
                ]
            }
