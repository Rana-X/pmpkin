"""MongoDB connection module."""

import os
import logging
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI")

client = None
db = None

if MONGODB_URI:
    client = MongoClient(MONGODB_URI, server_api=ServerApi("1"))
    db = client["pumpkin"]
else:
    logger.warning("MONGODB_URI not set – skipping MongoDB connection")


def ping_db():
    """Ping MongoDB to verify connectivity."""
    if client is None:
        logger.warning("MongoDB client not initialised – no URI configured")
        return False
    try:
        client.admin.command("ping")
        logger.info("Pinged your deployment. You successfully connected to MongoDB!")
        return True
    except Exception as e:
        logger.error("MongoDB connection failed: %s", e)
        return False
