#exceptions.py 
from fastapi import HTTPException, status

class UnauthorizedException(HTTPException):
    """
    Raised when authentication fails or token is missing/invalid.
    """
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

class ForbiddenException(HTTPException):
    """
    Raised when a user is authenticated but lacks permission.
    """
    def __init__(self, detail: str = "You do not have permission to perform this action"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)