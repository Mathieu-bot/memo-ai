import os
import json
import logging
import requests
from typing import Dict, Any
from openai import OpenAI
import tempfile

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables")

client = OpenAI(api_key=openai_api_key)

class AIService:
    @staticmethod
    def generate_quiz(course_title: str, course_description: str, num_questions: int = 5) -> Dict[str, Any]:
        """Generates a quiz based on the provided course."""
        prompt = f"""Generate a quiz with {num_questions} questions on the topic: {course_title}.

Course description: {course_description}

For each question, provide 4 possible answers, with only one being correct.
Return format:
{{
  "title": "Quiz title",
  "description": "Quiz description",
  "questions": [
    {{
      "text": "Question text",
      "explanation": "Explanation of the correct answer",
      "answers": [
        {{"text": "Answer 1", "is_correct": true}},
        {{"text": "Answer 2", "is_correct": false}},
        {{"text": "Answer 3", "is_correct": false}},
        {{"text": "Answer 4", "is_correct": false}}
      ]
    }},
    ...
  ]
}}
Ensure the response is a valid JSON object.
"""

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an assistant that generates educational quizzes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )

            content = response.choices[0].message.content.strip()
            logger.debug(f"OpenAI quiz response: {content}")
            quiz_data = json.loads(content)

            if not all(key in quiz_data for key in ["title", "description", "questions"]):
                raise ValueError("Invalid quiz format returned by OpenAI")

            return quiz_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse quiz response: {content}")
            raise ValueError(f"Failed to parse quiz response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while generating quiz: {str(e)}")
            raise ValueError(f"Unexpected error while generating quiz: {str(e)}")

    @staticmethod
    def generate_transcript(video_url: str) -> str:
        """Generates a transcript from the audio content of the video at the given URL."""
        try:
            # download videos temporary
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                response = requests.get(video_url, stream=True)
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_file_path = temp_file.name

            # Use Whisper API for transcription
            with open(temp_file_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )

            os.unlink(temp_file_path)
            return transcript.text if transcript.text else "Transcription not available"

        except requests.RequestException as e:
            logger.error(f"Failed to download video: {str(e)}")
            return "Transcription not available"
        except Exception as e:
            logger.error(f"Unexpected error while generating transcript: {str(e)}")
            return "Transcription not available"

    @staticmethod
    def generate_summary(content: str) -> str:
        """Generates a summary of the provided content."""
        prompt = f"Summarize the following content in 100-200 words:\n{content}"
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an assistant that generates concise summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.5
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Unexpected error while generating summary: {str(e)}")
            return "Summary not available"

    @staticmethod
    def generate_flashcards(content: str, num_cards: int = 10) -> list:
        """Generates flashcards from the provided content."""
        prompt = f"Generate {num_cards} flashcards from the following content:\n{content}\nEach flashcard should have a 'question' and 'answer'."
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an assistant that generates educational flashcards."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            content = response.choices[0].message.content.strip()
            flashcards = json.loads(content)
            return flashcards
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse flashcards response: {content}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error while generating flashcards: {str(e)}")
            return []