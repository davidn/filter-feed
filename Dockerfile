FROM python:3.9

ENV APP_HOME /app
WORKDIR $APP_HOME

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Monkey patch until https://github.com/bool-dev/Flask-Cloud-NDB/pull/2 is accepted
COPY cloud_ndb.patch ./
RUN patch -p1 -d $(pip show Flask | grep '^Location: ' | sed -e 's/Location: //') < cloud_ndb.patch 

COPY *.py ./
COPY templates ./templates/

CMD exec python3 -m gunicorn.app.wsgiapp --bind :$PORT --workers 6 --threads 1 app:app
