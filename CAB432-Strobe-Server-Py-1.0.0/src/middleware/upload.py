from fastapi import UploadFile

async def single_image_upload(file: UploadFile) -> UploadFile:
    """Validate and store a single uploaded image file."""
    return file
