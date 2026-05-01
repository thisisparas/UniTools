FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install LibreOffice for Word to PDF conversion
RUN apt-get update && apt-get install -y \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Create uploads folder
RUN mkdir -p uploads

# Expose port 5000
EXPOSE 5000

# Run the app
CMD ["python", "app.py"]
