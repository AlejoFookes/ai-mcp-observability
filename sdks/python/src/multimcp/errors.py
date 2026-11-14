class MultimcpError(Exception):
    """Base class for errors raised by multimcp itself, never by the wrapped provider SDK."""


class MultimcpConfigError(MultimcpError):
    """Invalid configuration or an unreadable price catalog."""
