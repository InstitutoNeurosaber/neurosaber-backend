import mimetypes
from uuid import uuid4

import boto3
import requests

from app.core.config import settings


class S3Service:
    def __init__(self, bucket_name):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.REGION_NAME,
        )

    def upload_image_from_binary(self, binary_data, key, img_format="jpeg"):
        if not key:
            key = uuid4().hex
        return self.upload_object(binary_data, f"{key}.{img_format}")

    def upload_image_from_url(self, url, key: str = None):
        try:
            binary = requests.get(url).content
            return self.upload_image_from_binary(binary, key=key)
        except Exception as e:
            print("Error uploading image from URL to S3:", str(e))

    def upload_object(self, content_bytes: bytes, key: str):
        """
        Upload an object (bytes) to S3.

        Args:
            content_bytes (bytes): The object data to upload.
            key (str): The key under which to store the object in S3.

        Returns:
            dict: Metadata about the uploaded object.
        """
        try:
            print("Uploading object to S3 with key:", key)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content_bytes,
                ContentType=self._infer_mime_type(key),
            )
            return key
        except Exception as e:
            # Handle exceptions appropriately
            raise e

    @staticmethod
    def _get_bytes_from_url(url):
        try:
            response = requests.get(url)
            response.raise_for_status()  # Check for any HTTP errors

            # Get the content as bytes
            content_bytes = response.content

            return content_bytes
        except Exception as e:
            # Handle exceptions appropriately
            raise e

    @staticmethod
    def _infer_mime_type(filename):
        """
        Infer the MIME type based on the filename.

        Args:
            filename (str): The name of the file.

        Returns:
            str: The inferred MIME type, or 'application/octet-stream' if unknown.
        """
        # Use mimetypes to guess the MIME type based on the file's extension
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type is None:
            return "application/octet-stream"
        return mime_type
