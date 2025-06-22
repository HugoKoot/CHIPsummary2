FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Create chats directory with proper permissions
RUN mkdir -p /app/chats && chmod 777 /app/chats

ENV FLASK_APP=app
ENV FLASK_ENV=development
ENV PYTHONPATH="${PYTHONPATH}:/app"

CMD ["flask", "--app", "app", "--debug", "run", "--host=0.0.0.0"] 