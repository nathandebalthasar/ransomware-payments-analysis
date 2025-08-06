import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] [%(threadName)s] %(message)s',
)
log = logging.getLogger(__name__)
