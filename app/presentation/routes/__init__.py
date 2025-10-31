"""
Routes module for Casterly Rock Simulation API.

This module contains all the API route handlers organized by domain.
"""

from .simulation_routes import router as simulation_router
from .reports_routes import router as reports_router

__all__ = ["simulation_router", "reports_router"]
