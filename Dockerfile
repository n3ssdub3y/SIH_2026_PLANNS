# NWIS-Sentinel | SIH 2026 | Hugging Face Spaces Dockerfile
# Python 3.11 slim — smaller base, faster build
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# System deps needed by chromadb, scipy, matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy all project files
COPY NLP/nlp_task_ddr/requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full project into /app
COPY NLP/nlp_task_ddr /app

# Hugging Face Spaces requires the app to listen on port 7860
ENV PORT=7860

# Expose port
EXPOSE 7860

# Start the gateway
CMD ["python", "gateway.py", "--no-browser"]
