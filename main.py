import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import profiling, dialogue, world, missions, npcs, events, saves
import config

app = FastAPI(title="RPG AI Framework", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Godot on localhost — tighten before any external deploy
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiling.router)
app.include_router(dialogue.router)
app.include_router(world.router)
app.include_router(missions.router)
app.include_router(npcs.router)
app.include_router(events.router)
app.include_router(saves.router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
