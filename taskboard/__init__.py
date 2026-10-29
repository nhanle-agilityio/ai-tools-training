"""TaskBoard - a small task management API used for Claude training."""

import os

from flask import Flask, jsonify

from . import db
from .errors import ConflictError, NotFoundError, ValidationError


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "taskboard.sqlite"),
        DEFAULT_PER_PAGE=10,
        MAX_PER_PAGE=50,
    )
    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    from .routes import bp

    app.register_blueprint(bp)

    @app.errorhandler(ValidationError)
    def handle_validation_error(err):
        return jsonify(error=str(err)), 400

    @app.errorhandler(NotFoundError)
    def handle_not_found(err):
        return jsonify(error=str(err)), 404

    @app.errorhandler(ConflictError)
    def handle_conflict(err):
        return jsonify(error=str(err)), 409

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app
