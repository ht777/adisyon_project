import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from models import create_tables
from pathlib import Path
from routers import products_new as products, orders, admin, auth, tables
from sqlalchemy.orm import Session
from models import get_session
import json
import asyncio
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
import logging
from contextlib import asynccontextmanager
from websocket_utils import set_connection_manager, broadcast_order_update

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get configuration from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./restaurant.db")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Static files directory (temporarily disabled)
STATIC_DIR = None  # str(Path(__file__).resolve().parents[1] / "frontend" / "static")

# --- YENİ EKLENEN KISIM BAŞLANGICI ---
# network_utils modülünü güvenli şekilde dahil et
try:
    from network_utils import set_static_ip
except ImportError:
    # Docker veya Linux ortamında hata vermesin diye boş fonksiyon tanımla
    def set_static_ip(): return True
# --- YENİ EKLENEN KISIM SONU ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Restaurant Order System...")
    
    # --- YENİ EKLENEN IP KONTROL BLOĞU ---
    if os.name == 'nt': # Sadece Windows sistemlerde çalışır
        try:
            logger.info("Checking network configuration...")
            # Not: Otomatik sabitleme işlemi genellikle run.py üzerinden yapılır
            # ancak burada da gerekirse loglama veya kontrol yapılabilir.
            pass 
        except Exception as e:
            logger.warning(f"IP setup check skipped: {e}")
    # -------------------------------------

    create_tables()
    logger.info("Database tables created/verified")

    # Static files temporarily disabled
    logger.info("Static files temporarily disabled for Docker deployment")

    yield

    # Shutdown
    logger.info("Shutting down Restaurant Order System...")

# Create FastAPI app
app = FastAPI(
    title="Restaurant Order System",
    version="1.0.0",
    description="Complete restaurant ordering system with real-time notifications",
    debug=DEBUG,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(tables.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.kitchen_connections: List[WebSocket] = []
        self.admin_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, client_type: str = "customer"):
        await websocket.accept()
        self.active_connections.append(websocket)

        if client_type == "kitchen":
            self.kitchen_connections.append(websocket)
        elif client_type == "admin":
            self.admin_connections.append(websocket)

        logger.info(f"WebSocket connected: {client_type} (Total: {len(self.active_connections)})")

    def disconnect(self, websocket: WebSocket, client_type: str = "customer"):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        if client_type == "kitchen" and websocket in self.kitchen_connections:
            self.kitchen_connections.remove(websocket)
        elif client_type == "admin" and websocket in self.admin_connections:
            self.admin_connections.remove(websocket)

        logger.info(f"WebSocket disconnected: {client_type} (Total: {len(self.active_connections)})")

    async def broadcast_to_all(self, message: dict):
        """Tüm bağlı istemcilere mesaj gönder"""
        if self.active_connections:
            message_json = json.dumps(message)
            # Aynı anda tüm bağlantılara gönder
            results = await asyncio.gather(
                *[self.send_message(connection, message_json) for connection in self.active_connections],
                return_exceptions=True
            )

            # Başarılı/başarısız istatistikleri
            success_count = sum(1 for r in results if r is None)
            logger.info(f"Broadcast to all: {success_count}/{len(self.active_connections)} successful")

    async def broadcast_to_kitchen(self, message: dict):
        """Mutfak ekranlarına mesaj gönder"""
        if self.kitchen_connections:
            message_json = json.dumps(message)
            results = await asyncio.gather(
                *[self.send_message(connection, message_json) for connection in self.kitchen_connections],
                return_exceptions=True
            )

            success_count = sum(1 for r in results if r is None)
            logger.info(f"Broadcast to kitchen: {success_count}/{len(self.kitchen_connections)} successful")

    async def broadcast_to_admin(self, message: dict):
        """Admin paneline mesaj gönder"""
        if self.admin_connections:
            message_json = json.dumps(message)
            results = await asyncio.gather(
                *[self.send_message(connection, message_json) for connection in self.admin_connections],
                return_exceptions=True
            )

            success_count = sum(1 for r in results if r is None)
            logger.info(f"Broadcast to admin: {success_count}/{len(self.admin_connections)} successful")

    async def send_message(self, websocket: WebSocket, message: str):
        """Tek bir bağlantıya mesaj gönder"""
        try:
            await websocket.send_text(message)
            return None
        except Exception as e:
            # Bağlantı kapalıysa, listeden kaldır
            # Check and remove from all connection lists, but avoid duplicate operations
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            if websocket in self.kitchen_connections:
                self.kitchen_connections.remove(websocket)
            if websocket in self.admin_connections:
                self.admin_connections.remove(websocket)

            logger.warning(f"Failed to send message: {e}")
            return e

manager = ConnectionManager()

# Set the connection manager for websocket utilities
set_connection_manager(manager)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    client_type = "customer"  # Default client type

    try:
        # Wait for the initial registration message to determine client type
        # Instead of immediately connecting as 'customer', wait for registration
        initial_data = await websocket.receive_text()
        try:
            initial_message = json.loads(initial_data)

            # If the first message is a registration, use the specified client type
            if initial_message.get("type") == "register":
                client_type = initial_message.get("client_type", "customer")
                # Connect with the specified client type immediately
                await manager.connect(websocket, client_type)
                logger.info(f"WebSocket registered as: {client_type}")
            else:
                # If first message isn't registration, connect as default and process the message later
                await manager.connect(websocket, client_type)
                # Process the initial message as normal
                if initial_message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
        except json.JSONDecodeError:
            # If initial message isn't valid JSON, connect as default
            await manager.connect(websocket, client_type)
            await websocket.send_text(json.dumps({"error": "Invalid JSON format"}))

        while True:
            # Client'tan gelen mesajları dinle
            data = await websocket.receive_text()
            try:
                message = json.loads(data)

                # Client tipini güncelle (only if it's a register message)
                if message.get("type") == "register":
                    old_type = client_type
                    client_type = message.get("client_type", "customer")
                    manager.disconnect(websocket, old_type)  # Eski tipi kaldır
                    await manager.connect(websocket, client_type)
                    logger.info(f"Client type changed: {old_type} -> {client_type}")

                # Diğer mesaj türlerini işle
                elif message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON format"}))

    except WebSocketDisconnect:
        manager.disconnect(websocket, client_type)
        logger.info(f"WebSocket disconnected: {client_type}")
    except Exception as e:
        manager.disconnect(websocket, client_type)
        logger.error(f"WebSocket error: {e}")

@app.get("/")
async def root():
    return {
        "message": "Restaurant Order System API",
        "version": "1.0.0",
        "environment": ENVIRONMENT,
        "debug": DEBUG
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "message": "Restaurant API is running"}

@app.get("/info")
async def system_info():
    """System information endpoint"""
    return {
        "app_name": "Restaurant Order System",
        "version": "1.0.0",
        "environment": ENVIRONMENT,
        "debug": DEBUG,
        "database_url": DATABASE_URL.replace("://.*@", "://*****@") if "@" in DATABASE_URL else DATABASE_URL,
        "cors_origins": CORS_ORIGINS,
        "static_directory": STATIC_DIR,
        "websocket_support": True,
        "features": [
            "Real-time order notifications",
            "QR code table management",
            "Multi-role authentication",
            "WebSocket communication",
            "File upload support",
            "Responsive design"
        ]
    }

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = DEBUG and ENVIRONMENT == "development"

    logger.info(f"Starting server on {host}:{port} (reload={reload})")
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info" if DEBUG else "warning"
    )