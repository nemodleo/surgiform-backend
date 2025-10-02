"""
Main entry point for the Surgiform application.
This module exports the FastAPI app instance for uvicorn.
"""

from surgiform.deploy.server import app

__all__ = ["app"]