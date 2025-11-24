from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import gradio as gr
import uvicorn
import os
import sys

# Ensure local modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test
import chat

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Full API Forwarding Layer for chat.py and test.py
# -------------------------------------------------------------------

# === chat.py API endpoints ===
@app.post("/update_chat")
async def update_chat_route(request: Request):
    return await chat.update_chat(request)

@app.post("/set_api_key_chat")
async def set_api_key_chat_route(request: Request):
    return await chat.set_api_key_chat(request)

@app.get("/unified_stream")
async def unified_stream_route():
    return await chat.unified_stream()

@app.post("/request_result")
async def request_result_route(request: Request):
    return await chat.request_result(request)


# === test.py API endpoints ===
@app.post("/update_code")
async def update_code_route(request: Request):
    return await test.update_code(request)

@app.get("/get_latest_code")
async def get_latest_code_route():
    return await test.get_latest_code()

@app.get("/get_api_key")
async def get_api_key_route():
    return await test.get_api_key_endpoint()

@app.post("/set_api_key")
async def set_api_key_route(request: Request):
    return await test.set_api_key_endpoint(request)

# Serve built frontend WITHOUT shadowing Gradio paths
from fastapi.responses import FileResponse

frontend_dir = os.path.join(os.path.dirname(__file__), "dist")
if not os.path.exists(frontend_dir):
    os.makedirs(frontend_dir)

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/bundle.js")
def serve_bundle():
    return FileResponse(os.path.join(frontend_dir, "bundle.js"))

# Optionally serve other built assets if needed
app.mount("/assets", StaticFiles(directory=frontend_dir), name="assets")

# Mount both Gradio interfaces
test_demo = test.get_gradio_interface()
chat_demo = chat.get_chat_gradio_interface()

# Mount the Gradio apps directly
app = gr.mount_gradio_app(app, test_demo, path="/gradio-test")
app = gr.mount_gradio_app(app, chat_demo, path="/gradio-chat")

print("new /gradio-test")
print("new /gradio-chat")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"[UNIFIED] running on http://127.0.0.1:{port}")
    print(f"- /gradio-test")
    print(f"- /gradio-chat")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="critical")
