from django.core.exceptions import ValidationError

MAX_IMAGE_MB = 5


def validate_image_size(file):
    if file.size > MAX_IMAGE_MB * 1024 * 1024:
        raise ValidationError(f"Rasm hajmi {MAX_IMAGE_MB} MB dan oshmasligi kerak.")
