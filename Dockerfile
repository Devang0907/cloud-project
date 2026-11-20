# Start with a small official Python image.
FROM python:3.12-slim

# Keep the app files together in /app inside the container.
WORKDIR /app

# Install the Python package used by the optional price refresh feature.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the dashboard code and its static files.
COPY . .

# The dashboard listens on port 8000.
EXPOSE 8000

# Start the dashboard when the container starts.
CMD ["python", "app.py", "--serve"]
