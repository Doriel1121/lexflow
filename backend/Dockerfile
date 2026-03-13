FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app/backend

# Install system dependencies for OCR and PDF processing
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-heb \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install any needed packages specified in requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app/backend
COPY . .

# Expose the port FastAPI runs on
EXPOSE 8000

# Run the application using Uvicorn
# Command to run uvicorn, app.main:app refers to the app object in app/main.py
# --host 0.0.0.0 makes the app accessible from outside the container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
