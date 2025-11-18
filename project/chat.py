import os
import re
import requests
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

# Gets FAKE code, meant for the LLM only and is not valid Python
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

def execute_mcp(mcp_call):
    """Execute MCP call using the actual Python function from test.py"""
    global stored_api_key, latest_blockly_chat_code

    if stored_api_key:
        os.environ["OPENAI_API_KEY"] = stored_api_key

    try:
        # Now, retrieve the real generated Python code from test.py
        blockly_code = ""
        try:
            resp = requests.get("http://localhost:7860/get_latest_code")
            if resp.ok:
                blockly_code = resp.json().get("code", "")
        except Exception as e:
            print(f"[WARN] Could not fetch real Python code: {e}")

        if not blockly_code.strip():
            return "No Python code available from test.py"

        # Parse the MCP call arguments
        match = re.match(r'create_mcp\((.*)\)', mcp_call.strip())
        if not match:
            return "Invalid MCP call format"

        params_str = match.group(1)
        user_inputs = []

        if params_str:
            import ast
            try:
                dict_str = "{" + params_str.replace("=", ":") + "}"
                param_dict = ast.literal_eval(dict_str)
                user_inputs = [str(v) for v in param_dict.values()]
            except Exception:
                for pair in params_str.split(','):
                    if '=' in pair:
                        _, value = pair.split('=', 1)
                        user_inputs.append(value.strip().strip('"').strip("'"))

        # Prepare to execute
        result = ""
        lines = blockly_code.split('\n')
        filtered_lines = []
        skip_mode = False
        in_demo_block = False

        for line in lines:
            if 'import gradio' in line:
                continue
            if 'demo = gr.Interface' in line:
                in_demo_block = True
                skip_mode = True
                continue
            elif 'demo.launch' in line:
                skip_mode = False
                in_demo_block = False
                continue
            elif in_demo_block:
                continue
            if 'gr.' in line:
                continue
            if not skip_mode:
                filtered_lines.append(line)

        code_to_run = '\n'.join(filtered_lines)

        def capture_result(msg):
            nonlocal result
            result = msg

        env = {
            "reply": capture_result,
            "__builtins__": __builtins__,
        }

        exec("import os", env)
        exec("import requests", env)
        exec("import json", env)

        exec(code_to_run, env)

        if "create_mcp" in env:
            import inspect
            sig = inspect.signature(env["create_mcp"])
            params = list(sig.parameters.values())

            typed_args = []
            for i, arg in enumerate(user_inputs):
                if i >= len(params):
                    break
                if arg is None or arg == "":
                    typed_args.append(None)
                    continue
                anno = params[i].annotation
                try:
                    if anno == int:
                        typed_args.append(int(float(arg)))
                    elif anno == float:
                        typed_args.append(float(arg))
                    elif anno == bool:
                        typed_args.append(str(arg).lower() in ("true", "1"))
                    elif anno == str or anno == inspect._empty:
                        typed_args.append(str(arg))
                    else:
                        typed_args.append(arg)
                except Exception:
                    typed_args.append(arg)

            result = env["create_mcp"](*typed_args)

        return result if result else "No output generated"

    except Exception as e:
        print(f"[MCP EXECUTION ERROR] {e}")
        import traceback
        traceback.print_exc()
        return f"Error executing MCP: {str(e)}"

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
are doing, state the goal or things. Remember, that info is just for you and you need to speak normally to the user.

Additionally, you have the ability to use the MCP yourself. Unlike normal OpenAI tools, you call this through chat. To do so, end your msg
(you cannot say anything after this) with:

```mcp
create_mcp(input_name=value)
```

Where you define all the inputs with set values and don't say outputs. And also notice how it doesn't say inputs(). This is just normal
Python code, not the special syntax.

So, if the user asks you to run the MCP, YOU HAVE THE ABILITY TO. DO NOT SAY THAT YOU CANNOT."""
    
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
            
            ai_response = response.choices[0].message.content
            
            # Check if the response contains ```mcp code block
            mcp_pattern = r'```mcp\n(.+?)\n```'
            mcp_match = re.search(mcp_pattern, ai_response, re.DOTALL)
            
            if mcp_match:
                # Extract MCP call
                mcp_call = mcp_match.group(1)
                
                # Filter out the MCP block from the displayed message
                displayed_response = ai_response[:mcp_match.start()].rstrip()
                
                print(f"[MCP DETECTED] Executing: {mcp_call}")
                
                # Execute the MCP call
                mcp_result = execute_mcp(mcp_call)
                
                print(f"[MCP RESULT] {mcp_result}")
                
                # Add MCP execution to history for context
                full_history.append({"role": "user", "content": message})
                full_history.append({"role": "assistant", "content": ai_response})
                full_history.append({"role": "system", "content": f"MCP execution result: {mcp_result}"})
                
                # Call GPT again with the MCP result
                try:
                    follow_up_response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": full_system_prompt},
                            *full_history,
                            {"role": "user", "content": "Please respond to the MCP execution result above and provide any relevant information to the user."}
                        ]
                    )
                    
                    # Combine the filtered initial response with the follow-up
                    final_response = displayed_response
                    if displayed_response:
                        final_response += "\n\n"
                    final_response += f"**MCP Execution Result:** {mcp_result}\n\n"
                    final_response += follow_up_response.choices[0].message.content
                    
                    return final_response
                except Exception as e:
                    return f"{displayed_response}\n\n**MCP Execution Result:** {mcp_result}\n\nError generating follow-up: {str(e)}"
            
            # No MCP block found, return normal response
            return ai_response
            
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