FROM python:3.7-slim

ENV APP_HOME /app
WORKDIR $APP_HOME

COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY *.py ./
COPY source-context.json ./

CMD exec python3 -m gunicorn.app.wsgiapp --bind :$PORT --workers 3 --threads 8 app:app
