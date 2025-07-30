import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
import base64
import tempfile
from typing import Dict, Any

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

class CloudinaryService:
    @staticmethod
    def upload_video(file_base64: str, resource_type: str = "video", folder: str = "course_videos") -> Dict[str, Any]:
        try:
            # Décodage de la chaîne Base64
            file_data = base64.b64decode(file_base64)

            # Création d'un fichier temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name

            # Upload vers Cloudinary
            result = cloudinary.uploader.upload(
                temp_file_path,
                resource_type=resource_type,
                folder=folder,
                overwrite=True,
                quality="auto",
                fetch_format="auto"
            )

            # Suppression du fichier temporaire
            os.unlink(temp_file_path)

            return {
                "public_id": result["public_id"],
                "url": result["url"],
                "secure_url": result["secure_url"],
                "format": result.get("format"),
                "resource_type": result["resource_type"],
                "duration": result.get("duration")
            }

        except Exception as e:
            print(f"Erreur lors du téléchargement sur Cloudinary: {e}")
            raise

    @staticmethod
    def delete_video(public_id: str, resource_type: str = "video") -> Dict[str, Any]:
        """Supprime une vidéo de Cloudinary."""
        try:
            result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            return result
        except Exception as e:
            print(f"Erreur lors de la suppression sur Cloudinary: {e}")
            raise
