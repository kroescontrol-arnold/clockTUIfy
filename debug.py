import logging
import json

# Enable or disable debug mode easily
DEBUG = False

# Setup logging only once
logging.basicConfig(
    filename='tuiclockify.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

def debug(message, data=None):
    if not DEBUG:
        return
    logging.debug(message)
    if data:
        # Pretty print JSON if possible
        try:
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
            logging.debug(pretty)
        except TypeError:
            # If not JSON serializable, just log raw
            logging.debug(data)

