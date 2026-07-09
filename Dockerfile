FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# db/ will be mounted as a persistent volume on fly.io
RUN mkdir -p /app/db/users

CMD ["python", "bot.py"]
