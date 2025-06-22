from flask import Flask
from flask_sse import sse
from flask_cors import CORS
from logging.handlers import HTTPHandler
from logging import Filter
import os


class ServiceNameFilter(Filter): # pragma: no cover
    def filter(self, record):
        record.service_name = "Website Backend"
        return True


def core_module_address(core_module):
    try:
        return os.environ[os.environ[core_module]]
    except KeyError:
        return None


def create_app(test=False):
    flask_app = Flask(__name__)
    CORS(flask_app)
    logger_address = core_module_address('LOGGER_MODULE')

    if logger_address and not test: # pragma: no cover
        http_handler = HTTPHandler(logger_address, "/log", method="POST")
        flask_app.logger.addFilter(ServiceNameFilter())
        flask_app.logger.addHandler(http_handler)

    triple_extractor_address = core_module_address('TRIPLE_EXTRACTOR_MODULE')
    if triple_extractor_address:
        flask_app.config['TRIPLE_EXTRACTOR_ADDRESS'] = triple_extractor_address 

    redis_address = os.environ.get("REDIS", None)
    if redis_address:
        flask_app.config['REDIS_ADDRESS'] = redis_address
        flask_app.config['REDIS_URL'] = f'redis://{redis_address}'

    from app.routes import bp
    flask_app.register_blueprint(bp)
    flask_app.register_blueprint(sse, url_prefix='/stream')

    return flask_app
