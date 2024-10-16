# Use the official Python image from the Docker Hub as the base image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt /app/requirements.txt

# Install system dependencies
RUN apt-get update && \
    apt-get install -y poppler-utils tesseract-ocr && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download necessary models for stanza, nltk, and spacy
RUN python -c "import stanza; stanza.download('fr', dir='/root/stanza_resources'); stanza.download('de', dir='/root/stanza_resources'); stanza.download('es', dir='/root/stanza_resources'); stanza.download('en', dir='/root/stanza_resources')"
RUN python -c "import nltk; nltk.download('omw-1.4', download_dir='/root/nltk_data'); nltk.download('wordnet', download_dir='/root/nltk_data')"
RUN python -c "import spacy; spacy.cli.download('en_core_web_lg')"

# Copy the rest of the application code into the container
COPY . /app

# Expose the port the app runs on
EXPOSE 8501

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the Streamlit application
CMD ["streamlit", "run", "clinfly_app_st.py", "--server.maxUploadSize", "1"]