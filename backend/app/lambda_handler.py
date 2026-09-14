"""AWS Lambda entrypoint for the SecureShop FastAPI service."""

from mangum import Mangum

from app.main import app

handler = Mangum(app, lifespan="auto")
