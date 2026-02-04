# Dockerfile for Discord Puzzle Trading Bot
# Includes system dependencies for OpenCV and Tesseract OCR

FROM python:3.11-slim

# Install system dependencies for OpenCV (libgl) and Tesseract
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure the data directory exists (will be used by the Fly volume)
RUN mkdir -p /data

# Run the bot
CMD ["python", "bot.py"]
