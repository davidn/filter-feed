#!/usr/bin/env python

import os

from flask import Flask, request
from main import handleHttp
from opencensus.ext.flask.flask_middleware import FlaskMiddleware

app = Flask(__name__)
FlaskMiddleware(app)
@app.route('/')
def entry():
    return handleHttp(request)




if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
