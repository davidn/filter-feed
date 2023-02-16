#!/bin/sh
PATH="$PATH:$HOME/.local/bin" python3 -m pytype app.py filter_feed.py model.py item.py view.py feed_admin.py
