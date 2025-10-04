# Stage 1: Builder - Install dependencies
FROM python:3.13-alpine AS builder

# Install build dependencies needed to compile Python packages
RUN apk add --no-cache gcc musl-dev

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime - Copy only what's needed
FROM python:3.13-alpine

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "asgi.py"]
