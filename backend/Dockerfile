# Use official Python runtime as base image
FROM python:3.12-slim

# Set working directory in container
WORKDIR /src

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src ./src
# Expose port 7860
EXPOSE 7860

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]