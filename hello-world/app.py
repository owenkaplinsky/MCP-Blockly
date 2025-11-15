from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr
import uvicorn
import asyncio
import threading
import os
from dotenv import load_dotenv

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

history = []
latest_blockly_code = ""
assistant_queue = asyncio.Queue()


async def reply(message):
    global history, assistant_queue
    history.append({"role": "assistant", "content": message})
    await assistant_queue.put(message)


@app.post("/update_code")
async def update_code(request: Request):
    global latest_blockly_code
    data = await request.json()
    latest_blockly_code = data.get("code", "")
    print("\n[FASTAPI] Updated Blockly code:\n", latest_blockly_code)
    return {"ok": True}


def execute_blockly_logic(user_message: str, loop):
    global latest_blockly_code, history
    if not latest_blockly_code.strip():
        return

    def safe_reply(msg):
        asyncio.run_coroutine_threadsafe(reply(msg), loop)

    env = {
        "reply": safe_reply,
        "history": history,
        "print": print,
    }

    try:
        exec(latest_blockly_code, env)
        if "on_user_send" in env:
            env["on_user_send"](user_message)
    except Exception as e:
        print("[EXECUTION ERROR]", e)


def run_blockly_thread(user_message):
    loop = asyncio.get_running_loop()
    thread = threading.Thread(target=execute_blockly_logic, args=(user_message, loop))
    thread.start()


def build_interface():
    with gr.Blocks() as demo:
        chatbot = gr.Chatbot(type="messages", label="Assistant", group_consecutive_messages=False)
        msg = gr.Textbox(placeholder="Type a message and press Enter")

        async def process_message(message):
            global history, assistant_queue
            history.append({"role": "user", "content": message})
            print(f"[USER] {message!r}")
            yield "", history

            while not assistant_queue.empty():
                assistant_queue.get_nowait()

            run_blockly_thread(message)

            while True:
                try:
                    reply_text = await asyncio.wait_for(assistant_queue.get(), timeout=2)
                    print(f"[ASSISTANT STREAM] {reply_text!r}")
                    yield "", history
                except asyncio.TimeoutError:
                    break

        msg.submit(process_message, [msg], [msg, chatbot], queue=True)
        clear_btn = gr.Button("Reset chat")
        clear_btn.click(lambda: ([], ""), None, [chatbot, msg], queue=False)

    return demo


demo = build_interface()
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    print("[BOOT] Running Gradio+FastAPI combo on http://127.0.0.1:7860")
    uvicorn.run(app, host="0.0.0.0", port=7860)
