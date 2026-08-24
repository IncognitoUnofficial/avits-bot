# exceptions.py
"""Custom exceptions for the AVITS login bot."""


class AVITSBotError(Exception):
    """Base exception for the bot."""
    pass


class DriverInitError(AVITSBotError):
    """Raised when Chrome driver fails to start."""
    pass


class LoginError(AVITSBotError):
    """Raised when login fails."""
    pass


class TokenExtractionError(AVITSBotError):
    """Raised when tokens cannot be extracted from the response."""
    pass


class CaptchaTimeoutError(AVITSBotError):
    """Raised when CAPTCHA is not solved within the timeout."""
    pass