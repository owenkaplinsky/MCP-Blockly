from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr
import uvicorn
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

latest_blockly_code = ""


@app.post("/update_code")
async def update_code(request: Request):
    global latest_blockly_code
    data = await request.json()
    latest_blockly_code = data.get("code", "")
    print("\n[FASTAPI] Updated Blockly code:\n", latest_blockly_code)
    return {"ok": True}


def execute_blockly_logic(user_inputs):
    global latest_blockly_code
    if not latest_blockly_code.strip():
        return "No Blockly code available"

    result = ""
    
    def capture_result(msg):
        nonlocal result
        result = msg

    env = {
        "reply": capture_result,
    }

    try:
        exec(latest_blockly_code, env)
        if "create_mcp" in env:
            # If create_mcp function exists, call it with the input arguments
            # Filter out None values and convert to list for unpacking
            args = [arg for arg in user_inputs if arg is not None]
            result = env["create_mcp"](*args)
        elif "process_input" in env:
            env["process_input"](user_inputs)
    except Exception as e:
        print("[EXECUTION ERROR]", e)
        result = f"Error: {str(e)}"

    return result if result else "No output generated"


def build_interface():
    with gr.Blocks() as demo:
        gr.Markdown("# Blockly Code Executor")
        
        # Create a fixed number of potential input fields (max 10)
        input_fields = []
        input_labels = []
        input_group_items = []
        
        with gr.Accordion("MCP Inputs", open=True):
            for i in range(10):
                # Create inputs that can be shown/hidden
                txt = gr.Textbox(label=f"Input {i+1}", visible=False)
                input_fields.append(txt)
                input_group_items.append(txt)
        
        output_text = gr.Textbox(label="Output", interactive=False)
        
        with gr.Row():
            submit_btn = gr.Button("Submit")
            refresh_btn = gr.Button("Refresh Inputs")

        def refresh_inputs():
            global latest_blockly_code
            
            # Parse the Python code to extract function parameters
            import re
            
            # Look for the create_mcp function definition
            pattern = r'def create_mcp\((.*?)\):'
            match = re.search(pattern, latest_blockly_code)
            
            params = []
            if match:
                params_str = match.group(1)
                if params_str.strip():
                    # Parse parameters to extract names and types
                    for param in params_str.split(','):
                        param = param.strip()
                        if ':' in param:
                            name, type_hint = param.split(':')
                            params.append({
                                'name': name.strip(),
                                'type': type_hint.strip()
                            })
                        else:
                            params.append({
                                'name': param,
                                'type': 'str'
                            })
            
            # Generate visibility and label updates for each input field
            updates = []
            for i, field in enumerate(input_fields):
                if i < len(params):
                    # Show this field and update its label
                    param = params[i]
                    updates.append(gr.update(
                        visible=True,
                        label=f"{param['name']} ({param['type']})"
                    ))
                else:
                    # Hide this field
                    updates.append(gr.update(visible=False))
            
            return updates

        def process_input(*args):
            # Get the input values from Gradio fields
            return execute_blockly_logic(args)

        # When refresh is clicked, update input field visibility and labels
        refresh_btn.click(
            refresh_inputs,
            outputs=input_fields,
            queue=False
        )
        
        submit_btn.click(
            process_input,
            inputs=input_fields,
            outputs=[output_text]
        )

    return demo


demo = build_interface()
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    print("[BOOT] Running Gradio+FastAPI combo on http://127.0.0.1:7860")
    uvicorn.run(app, host="0.0.0.0", port=7860)
