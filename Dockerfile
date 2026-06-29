# Use an official lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies (if any are added later)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server script into the container
COPY app.py .

# Expose port 5005 for target and viewer TCP connections
EXPOSE 5005

# Run the server script with unbuffered output so logs appear instantly on Render
CMD ["python", "-u", "app.py"]