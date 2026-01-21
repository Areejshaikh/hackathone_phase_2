import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.logger import logger
from fastapi.responses import RedirectResponse

from src.api import auth, tasks
from src.middleware.jwt_middleware import JWTMiddleware
from init_db import create_db_and_tables

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_db_and_tables()
    yield
    # Shutdown (if needed)

app = FastAPI(
    title="Todo Backend API",
    lifespan=lifespan
)

# Add JWT middleware (should be added before other middlewares)
app.add_middleware(JWTMiddleware)

# Add security headers
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response: Response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
            return response
        except Exception as e:
            # Handle anyio.EndOfStream and other connection errors gracefully
            from anyio import EndOfStream
            if isinstance(e, EndOfStream):
                # Connection was closed by client, return empty response
                return Response(status_code=499)
            # Re-raise other exceptions
            raise

# Rate limiting middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_requests_per_minute=30, non_auth_requests_per_minute=100):
        super().__init__(app)
        self.auth_requests_per_minute = auth_requests_per_minute
        self.non_auth_requests_per_minute = non_auth_requests_per_minute
        self.requests = {}

    async def dispatch(self, request, call_next):
        try:
            client_ip = request.client.host
            path = request.url.path

            # Determine rate limit based on request type
            # Auth endpoints have stricter limits
            is_auth_request = path.startswith('/api/auth/')
            limit = self.auth_requests_per_minute if is_auth_request else self.non_auth_requests_per_minute

            # Clean old requests (older than 1 minute)
            now = time.time()
            if client_ip in self.requests:
                self.requests[client_ip] = [
                    (req_time, req_path) for req_time, req_path in self.requests[client_ip]
                    if now - req_time < 60
                ]

            # Add current request
            if client_ip not in self.requests:
                self.requests[client_ip] = []
            self.requests[client_ip].append((now, path))

            # Count requests of the same type
            if is_auth_request:
                recent_requests = [(time, req_path) for time, req_path in self.requests[client_ip]
                                  if req_path.startswith('/api/auth/')]
            else:
                recent_requests = [(time, req_path) for time, req_path in self.requests[client_ip]
                                  if not req_path.startswith('/api/auth/')]

            if len(recent_requests) > limit:
                return Response(
                    content=f"Rate limit exceeded. {limit} requests per minute allowed.",
                    status_code=429,
                    headers={
                        "Retry-After": "60"
                    }
                )

            response = await call_next(request)
            return response
        except Exception as e:
            # Handle anyio.EndOfStream and other connection errors gracefully
            from anyio import EndOfStream
            if isinstance(e, EndOfStream):
                # Connection was closed by client, return empty response
                return Response(status_code=499)
            # Re-raise other exceptions
            raise

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, auth_requests_per_minute=30, non_auth_requests_per_minute=100)  # Differentiated rate limits


# Middleware to handle trailing slashes consistently
@app.middleware("http")
async def add_trailing_slash_middleware(request: Request, call_next):
    path = request.url.path

    # 1. Exclude API routes from trailing slash redirects (critical for POST/PUT/PATCH/DELETE requests)
    if path.startswith('/api/'):
        return await call_next(request)

    # 2. Sirf GET requests ko redirect karein (Docs aur simple pages ke liye)
    # 3. POST/PUT/PATCH/DELETE requests ko kabhi redirect na karein (especially for API routes)
    if request.method != "GET":
        return await call_next(request)

    # 4. Exclude Docs and static files
    excluded_paths = ["/docs", "/redoc", "/openapi.json"]
    if path in excluded_paths or path.endswith(('.js', '.css', '.png', '.jpg', '.ico')):
        return await call_next(request)

    # 5. Add trailing slash only for GET requests if missing (non-API routes)
    if not path.endswith('/') and path != '/':
        new_path = path + '/'
        if request.url.query:
            new_path += '?' + request.url.query
        return RedirectResponse(url=new_path, status_code=307)

    response = await call_next(request)
    return response
# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])

@app.get("/")
def read_root():
    return {"status": "online", "message": "Backend is working perfectly!"}

from fastapi.responses import JSONResponse

# Error handlers
@app.exception_handler(401)
async def unauthorized_handler(request, exc):
    return JSONResponse(
        status_code=401,
        content={"detail": "Unauthorized"}
    )

@app.exception_handler(403)
async def forbidden_handler(request, exc):
    return JSONResponse(
        status_code=403,
        content={"detail": "Forbidden"}
    )

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Not found"}
    )


# Global handler for anyio.EndOfStream (client disconnected)
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    from anyio import EndOfStream
    if isinstance(exc, EndOfStream):
        # Client disconnected before response was sent
        return Response(status_code=499, content="")
    # Re-raise other exceptions to let default handlers deal with them
    raise exc


# Add CORS middleware with proper configuration for trailing slashes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hackathone-phase-2.vercel.app",
        "http://localhost:3000"
    ],  # Allow React dev server and other origins as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Expose headers for client access
    expose_headers=["Access-Control-Allow-Origin", "Authorization"]
)
