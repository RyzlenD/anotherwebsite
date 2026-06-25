# 1. Use an official lightweight Python image
FROM python:3.10-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy the dependencies file first (optimizes Docker caching)
COPY requirements.txt .

# 4. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your local project files into the container
COPY . .

# 6. Expose the port Flask/Gunicorn will run on
EXPOSE 5000

# 7. Start command using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]