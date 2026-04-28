import requests
from config import (
    CLOUDFLARE_ACCOUNT_ID,
    CLOUDFLARE_API_TOKEN,
    CLOUDFLARE_DATABASE_ID,
)


def store_cloudflare(pdf_name, chunk_id, text):

    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/d1/database/{CLOUDFLARE_DATABASE_ID}/query"

    query = f"""
    INSERT INTO pdf_chunks (pdf_name, chunk_id, text)
    VALUES ('{pdf_name}', {chunk_id}, '{text}')
    """

    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    requests.post(
        url,
        headers=headers,
        json={"sql": query}
    )
    
