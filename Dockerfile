# 1. Start from an official Python base image
FROM python:3.9-slim-buster

# 2. Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app/main.py
ENV FLASK_RUN_HOST=0.0.0.0

# 3. Set the working directory
WORKDIR /app

# 4. Copy requirements.txt and install dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the application code into the image
# The app directory contains main.py and __init__.py
COPY app/ ./app/

# 6. Expose the port
EXPOSE 5000

# 7. Define the command to run the application
CMD ["python", "./app/main.py"]
