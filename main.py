"""
Main entry point for BCN Art Compass.

This is the entry point for starting the multi-agent cultural events
recommender system. For now, it starts the FastAPI server.
"""

import uvicorn

from observability import configure_logging, log_info


def main() -> None:
    """Main entry point for the application."""
    configure_logging()
    log_info("starting_application", service="bcn-art-compass")

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
