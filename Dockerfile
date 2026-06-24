FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 50002

CMD ["gunicorn", "--bind", "0.0.0.0:50002", "app:app"]
