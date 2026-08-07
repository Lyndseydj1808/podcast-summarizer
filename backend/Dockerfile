# Start from an official, minimal Python image rather than a full OS.
FROM python:3.14-slim

# Whisper chunking needs ffmpeg installed at the system level, same as on
# your own machine, apt-get is Debian's package manager (this base image is
# Debian-based), the Python equivalent of the winget install we did locally.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# All following commands run from this folder inside the container.
WORKDIR /app

# Copy just the dependency list first and install it before copying the rest
# of the code. Docker caches each step, so as long as requirements.txt hasn't
# changed, rebuilds skip reinstalling everything and stay fast.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the actual application code.
COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
