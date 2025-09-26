from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

# Load environment variables
load_dotenv()

# Import database models and session
from app.models.base import init_db, get_db
from app.models.models import Customer, Manufacturer, Part, Call, Quote, Order

# Initialize FastAPI app
app = FastAPI(
    title="Quote Agent IMS",
    description="An Inventory Management System with AI agent for handling calls",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Import routes
from app.routes import twilio_routes, dashboard_routes, email_routes

# Include routers
app.include_router(twilio_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(email_routes.router)

# Startup event to initialize database
@app.on_event("startup")
async def startup_event():
    """
    Initialize database on startup
    """
    await init_db()

@app.get("/")
async def root(request: Request):
    """
    Root endpoint that returns a welcome message
    """
    return {"message": "Welcome to Quote Agent IMS API"}

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint that also checks database connection
    """
    try:
        # Test database connection
        await db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
