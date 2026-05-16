import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import HOST, PORT
from api.routes.game import router as game_router
from api.routes.dialogue import router as dialogue_router
from api.routes.missions import router as missions_router
from api.routes.world import router as world_router

app = FastAPI(
    title="RPG AI Framework",
    description="AI-powered backend for a randomized open-world RPG. Connects to Godot 4 frontend.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(game_router)
app.include_router(dialogue_router)
app.include_router(missions_router)
app.include_router(world_router)


@app.get("/")
async def root():
    return {
        "name": "RPG AI Framework",
        "version": "0.1.0",
        "status": "running",
        "godot_api_contract": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
