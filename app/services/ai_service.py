import openai
import os
import json
from typing import Dict, Any

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables")

openai.api_key = openai_api_key

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
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an assistant that generates educational quizzes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )

            content = response.choices[0].message.content.strip()
            quiz_data = json.loads(content)

            if not all(key in quiz_data for key in ["title", "description", "questions"]):
                raise ValueError("Invalid quiz format returned by OpenAI")

            return quiz_data

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse quiz response: {str(e)}")
        except openai.error.OpenAIError as e:
            raise ValueError(f"OpenAI API error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Unexpected error while generating quiz: {str(e)}")

    @staticmethod
    def generate_transcript(video_url: str) -> str:
        """Generates a transcript from the audio content of the video at the given URL."""
        prompt = f"""You are an AI assistant capable of transcribing audio from a video. 
The video is located at this URL: {video_url}. 
Based on the content of this educational video, provide a textual transcript of the spoken content. 
Return the transcript as a plain text string. If the transcription fails or the content is unclear, return 'Transcription not available'.
"""

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an AI that transcribes educational video content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3 
            )

            transcript = response.choices[0].message.content.strip()
            if not transcript or "transcription not available" in transcript.lower():
                return "Transcription not available"
            return transcript

        except openai.error.OpenAIError as e:
            raise ValueError(f"OpenAI API error during transcription: {str(e)}")
        except Exception as e:
            raise ValueError(f"Unexpected error while generating transcript: {str(e)}")