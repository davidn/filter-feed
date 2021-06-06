#!/bin/sh
PATH="$PATH:$HOME/.local/bin" python3 -m pytype app.py main.py filter_feed.py create_feed.py
