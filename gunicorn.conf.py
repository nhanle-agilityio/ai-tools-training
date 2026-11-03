import os

bind = f"0.0.0.0:{os.environ.get('PORT') or '5050'}"
workers = 2
preload_app = True
accesslog = "-"
