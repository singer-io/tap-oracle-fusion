class OracleFusionError(Exception):
    """class representing Generic Http error."""

    def __init__(self, message=None, response=None):
        super().__init__(message)
        self.message = message
        self.response = response


class OracleFusionBackoffError(OracleFusionError):
    """class representing backoff error handling."""
    pass

class OracleFusionBadRequestError(OracleFusionError):
    """class representing 400 status code."""
    pass

class OracleFusionUnauthorizedError(OracleFusionError):
    """class representing 401 status code."""
    pass


class OracleFusionForbiddenError(OracleFusionError):
    """class representing 403 status code."""
    pass

class OracleFusionNotFoundError(OracleFusionError):
    """class representing 404 status code."""
    pass

class OracleFusionConflictError(OracleFusionError):
    """class representing 406 status code."""
    pass

class OracleFusionUnprocessableEntityError(OracleFusionBackoffError):
    """class representing 409 status code."""
    pass

class OracleFusionRateLimitError(OracleFusionBackoffError):
    """class representing 429 status code."""
    def __init__(self, message=None, response=None):
        """Initialize the Amazon_AdsRateLimitError. Parses the 'Retry-After' header from the response (if present) and sets the
            `retry_after` attribute accordingly.
        """
        self.response = response

        # Retry-After header parsing
        retry_after = None
        if response and hasattr(response, 'headers'):
            raw_retry = response.headers.get('Retry-After')
            if raw_retry:
                try:
                    retry_after = int(raw_retry)
                except ValueError:
                    retry_after = None

        self.retry_after = retry_after
        base_msg = message or "Rate limit hit"
        retry_info = f"(Retry after {self.retry_after} seconds.)" \
            if self.retry_after is not None else "(Retry after unknown delay.)"
        full_message = f"{base_msg} {retry_info}"
        super().__init__(full_message, response=response)

class OracleFusionInternalServerError(OracleFusionBackoffError):
    """class representing 500 status code."""
    pass

class OracleFusionNotImplementedError(OracleFusionBackoffError):
    """class representing 501 status code."""
    pass

class OracleFusionBadGatewayError(OracleFusionBackoffError):
    """class representing 502 status code."""
    pass

class OracleFusionServiceUnavailableError(OracleFusionBackoffError):
    """class representing 503 status code."""
    pass

ERROR_CODE_EXCEPTION_MAPPING = {
    400: {
        "raise_exception": OracleFusionBadRequestError,
        "message": "A validation exception has occurred."
    },
    401: {
        "raise_exception": OracleFusionUnauthorizedError,
        "message": "The access token provided is expired, revoked, malformed or invalid for other reasons."
    },
    403: {
        "raise_exception": OracleFusionForbiddenError,
        "message": "You are missing the following required scopes: read"
    },
    404: {
        "raise_exception": OracleFusionNotFoundError,
        "message": "The resource you have specified cannot be found."
    },
    409: {
        "raise_exception": OracleFusionConflictError,
        "message": "The API request cannot be completed because the requested operation would conflict with an existing item."
    },
    422: {
        "raise_exception": OracleFusionUnprocessableEntityError,
        "message": "The request content itself is not processable by the server."
    },
    429: {
        "raise_exception": OracleFusionRateLimitError,
        "message": "The API rate limit for your organisation/application pairing has been exceeded."
    },
    500: {
        "raise_exception": OracleFusionInternalServerError,
        "message": "The server encountered an unexpected condition which prevented" \
            " it from fulfilling the request."
    },
    501: {
        "raise_exception": OracleFusionNotImplementedError,
        "message": "The server does not support the functionality required to fulfill the request."
    },
    502: {
        "raise_exception": OracleFusionBadGatewayError,
        "message": "Server received an invalid response."
    },
    503: {
        "raise_exception": OracleFusionServiceUnavailableError,
        "message": "API service is currently unavailable."
    }
}

