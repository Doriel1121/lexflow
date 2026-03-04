# Use an official Python runtime as a parent image
FROM python:3.11-slim-buster

# Set the working directory in the container
WORKDIR /app/backend

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
