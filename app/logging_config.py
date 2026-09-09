import logging


def configure_logging() -> None:
    """Configure console logging for the application.

    uvicorn's default logging config does not configure the *root* logger, so
    INFO messages emitted by app loggers (e.g. the email-verification token
    printed on request) would otherwise be silently dropped. This is a no-op
    when a root handler already exists (e.g. inside pytest, which installs its
    own capture handler).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
    )
    # SQLAlchemy installs its own handler when `echo=True`; avoid double output.
    logging.getLogger("sqlalchemy").propagate = False
