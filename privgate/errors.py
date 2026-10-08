class PrivGateError(Exception):
    """Base class for all errors raised by this package."""


class PrivacyLeakError(PrivGateError):
    """An original sensitive value was still present in the text about to be sent (fail-closed)."""


class LLMError(PrivGateError):
    """The language-model call failed."""


class LLMConfigError(LLMError):
    """The LLM client is not configured (for example a missing API key)."""


class InputTooLongError(PrivGateError):
    """The input is longer than the configured limit."""
