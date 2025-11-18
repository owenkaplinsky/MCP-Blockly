import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import uvicorn
import gradio as gr

# Initialize OpenAI client (will be updated when API key is set)
client = None

# Store API key in memory for this process
stored_api_key = ""

# Global variable to store the latest chat context
latest_blockly_chat_code = ""

# FastAPI App
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/update_chat")
async def update_chat(request: Request):
    global latest_blockly_chat_code
    data = await request.json()
    latest_blockly_chat_code = data.get("code", "")
    print("\n[FASTAPI] Updated Blockly chat code:\n", latest_blockly_chat_code)
    return {"code": latest_blockly_chat_code}

@app.post("/set_api_key_chat")
async def set_api_key_chat(request: Request):
    """Receive API key from frontend and store it"""
    global stored_api_key
    data = await request.json()
    api_key = data.get("api_key", "").strip()
    
    # Store in memory and set environment variable for this process
    stored_api_key = api_key
    os.environ["OPENAI_API_KEY"] = api_key
    
    print(f"[CHAT API KEY] Set OPENAI_API_KEY in chat.py environment")
    return {"success": True}

def create_gradio_interface():
    # Hardcoded system prompt
    SYSTEM_PROMPT = """You are an AI assistant created to help with Blockly MCP tasks. Users can create MCP (multi-context-protocol) servers
by using premade Blockly blocks. MCP is a standardized tool method for AI systems, where it defines inputs and outputs and allows any LLM to
call the custom made tool. You will receive the current state of the workspace in the next message. Here is the format for most blocks:
`block_name(inputs(input_name: value))`. But, for `create_mcp` and `func_def`, they have their own format:
`block_name(inputs(input_name: type), outputs(output_name: value))`. MCP and Func blocks are unique because they define custom functions
or the MCP server itself. If a block is inside of another block (like code, rather than returning a value, such as a loop), it will be
indented below a block with one tab. For `value`, a value returning block can be inside of another block, so you may see multiple blocks
nested within each other.

Your goal is to help the user with coding questions and explicitly stay on topic. Note that the format `block_name... etc.` is made custom
for you (the assistant) and is not visible to the user - so do not use this format when communicating with them.

When the user asks questions or talks about their project, don't talk like a robot. This means a few things:
- Do not say "multi-context-protocol" just say MCP
- When talking about their project, talk in natural language. Such as if they ask what their project is doing, don't say what the blocks
are doing, state the goal or things. Remember, that info is just for you and you need to speak normally to the user."""
    
    def chat_with_context(message, history):
        # Check if API key is set and create/update client
        global client, stored_api_key
        
        # Use stored key or check environment
        api_key = stored_api_key or os.environ.get("OPENAI_API_KEY")
        
        if api_key and (not client or (hasattr(client, 'api_key') and client.api_key != api_key)):
            try:
                client = OpenAI(api_key=api_key)
            except Exception as e:
                return f"Error initializing OpenAI client: {str(e)}"
        
        if not client or not api_key:
            return "OpenAI API key not configured. Please set it in File > Settings in the Blockly interface."
        
        # Get the chat context from the global variable
        global latest_blockly_chat_code
        context = latest_blockly_chat_code
        
        # Convert history to OpenAI format
        full_history = []
        for human, ai in history:
            full_history.append({"role": "user", "content": human})
            full_history.append({"role": "assistant", "content": ai})

        # Debug: Print context to see what we're getting
        print(f"[DEBUG] Context received: {context if context else 'No context available'}")

        # Combine system prompt with context
        full_system_prompt = SYSTEM_PROMPT
        if context:
            full_system_prompt += f"\n\nCurrent Blockly workspace state:\n{context}"
        else:
            full_system_prompt += "\n\nNote: No Blockly workspace context is currently available."

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": full_system_prompt},
                    *full_history,
                    {"role": "user", "content": message}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {str(e)}"
    
    # Create the standard ChatInterface
    demo = gr.ChatInterface(
        fn=chat_with_context,
        title="Blockly MCP Chat",
    )

    return demo

# Mount Gradio with FastAPI
demo = create_gradio_interface()
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    print("[BOOT] Running Gradio+FastAPI Chat on http://127.0.0.1:7861")
    uvicorn.run(app, host="0.0.0.0", port=7861)