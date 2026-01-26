# Use slim Python image
FROM python:3.13-slim

# Set working directory
WORKDIR /code

# Copy requirements first (leverages Docker cache)
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy the rest of the code
COPY . .

# Set ENTRYPOINT to python so we can call scripts directly in docker-compose
ENTRYPOINT ["python"]