import asyncio
import os
from typing import List
from dotenv import load_dotenv
import google.generativeai as genai

async def main():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("No GEMINI_API_KEY found.")
        return
        
    genai.configure(api_key=api_key)
    try:
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content="Hello world",
            task_type="retrieval_document"
        )
        print(f"Success gemini-embedding-001! Length is: {len(result['embedding'])}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
