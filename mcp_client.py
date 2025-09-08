import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
import asyncio
from dotenv import load_dotenv
import gradio as gr
import logging
import uuid
from typing import Dict, List, Optional
from datetime import datetime

# Set up logging to debug issues
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Enhanced system prompt with state awareness
system_prompt = """
You are an AI assistant specialized in creating and managing websites using HTML and Tailwind CSS,If the design requires images, use the mcp tool to get images from my local directory is you didn't found nothing usful use free placeholder images from sources like Unsplash, Pexels, Picsum, with the help of Netlify tools. Your primary goal is to assist users in building, updating, and deploying websites efficiently.

IMPORTANT: You have persistent memory across conversations. When users ask for modifications, always build upon previous work rather than starting from scratch.

You have access to the following tools (use these EXACT names):
- `gradio:check_netlify_cli`: Check if the Netlify CLI is installed
- `gradio:install_netlify_cli`: Install the Netlify CLI if not already installed
- `gradio:login_netlify`: Log in to Netlify
- `gradio:deploy_netlify`: Deploy the site to Netlify and extract the URL
- `gradio:extract_code_blocks`: Extract code blocks from markdown text. Parameters: 'text' (markdown content), 'lang' (programming language like 'html', 'css')
- `gradio:save_code_to_path`: Save code to a file. Parameters: 'the_extracted_code_blocks' (the actual code content), 'name_of_the_file' (filename like 'index.html')
- `gradio:display_the_website`: Display the website in the default web browser
- `gradio:go_to_project_folder_for_deployment`: Change the working directory to the project folder that contain my website files to execute the deployment command.

MEMORY AND STATE MANAGEMENT:
1. Your conversation state is automatically saved after each interaction
2. When users request modifications, refer to previous messages in this conversation
3. Build upon existing code rather than recreating from scratch
4. If this is the first message in a thread, create new website files
5. If there are previous messages, assume files exist and modify them accordingly

MODIFICATION KEYWORDS TO WATCH FOR:
- "change", "modify", "update", "edit", "alter", "adjust"
- "add", "remove", "delete", "insert"
- "make it", "turn it into", "convert to"
- "instead of", "replace", "swap"
- Color changes: "make it red", "change to blue"
- Layout changes: "center it", "move to left", "add padding"
- Style changes: "make it bigger", "add shadow", "round corners"

IMPORTANT: When saving code, you must provide the ACTUAL CODE CONTENT to 'the_extracted_code_blocks', not just a reference or language type.

When creating or modifying a website, follow these steps:
1. Check if this is a modification request by looking at conversation history
2. For modifications: Build upon the existing code structure from previous messages
3. For new websites: Generate fresh HTML/CSS code based on user requirements
4. For each code block (HTML, CSS, etc.):
   - Use `gradio:save_code_to_path` directly with the actual code content and filename
   - Do NOT use extract_code_blocks unless you're working with markdown text
5. Use `gradio:display_the_website` to show the website
6. Optionally deploy to Netlify:
   - Check CLI: `gradio:check_netlify_cli`
   - Install if needed: `gradio:install_netlify_cli`
   - Login: `gradio:login_netlify`
   - Go to project folder: `gradio:go_to_project_folder_for_deployment`
   - Deploy: `gradio:deploy_netlify`

Always provide clear feedback about what you're doing at each step and whether you're modifying existing code or creating new code.

Remember: Your state persists across messages, so you can reference and build upon previous work seamlessly!
"""

class WebsiteSessionManager:
    """Manages session IDs and website project context"""
    
    def __init__(self):
        self.current_session_id: Optional[str] = None
        self.project_description: str = ""
        
    def start_new_session(self) -> str:
        """Start a new website project session"""
        self.current_session_id = str(uuid.uuid4())
        self.project_description = ""
        logger.info(f"Started new session: {self.current_session_id}")
        return self.current_session_id
        
    def get_current_session(self) -> Optional[str]:
        """Get current session ID"""
        return self.current_session_id
        
    def set_project_description(self, description: str):
        """Set the current project description"""
        self.project_description = description

# Global instances
session_manager = WebsiteSessionManager()
memory_saver = MemorySaver()  # LangGraph's built-in memory checkpointer
agent = None

# Async setup function to initialize the agent with MemorySaver
async def setup():
    try:
        # Define the MCP server configuration
        mcp_config = {
            "gradio": {
                "url": "http://127.0.0.1:7860/gradio_api/mcp/sse",
                "transport": "sse"
            }
        }
        
        logger.info("Initializing MCP client...")
        # Initialize the MultiServerMCPClient
        client = MultiServerMCPClient(mcp_config)
        
        # Load tools from the MCP server
        logger.info("Loading tools from MCP server...")
        tools = await client.get_tools()
        logger.info(f"Loaded {len(tools)} tools: {[tool.name for tool in tools]}")
        
        # Initialize the Gemini model
        logger.info("Initializing Gemini model...")
        model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            google_api_key=os.environ["GOOGLE_API_KEY"],
            temperature=0.1  # Lower temperature for more consistent code generation
        )
        
        # Create the ReAct agent with MemorySaver checkpointer
        logger.info("Creating ReAct agent with MemorySaver checkpointer...")
        agent = create_react_agent(
            model, 
            tools,
            checkpointer=memory_saver  # This enables automatic state persistence!
        )
        logger.info("Agent with memory checkpointer setup complete!")
        
        return agent
        
    except Exception as e:
        logger.error(f"Error during setup: {e}")
        raise Exception(f"Setup failed: {e}")

# Initialize agent on startup
async def init_agent():
    global agent
    if agent is None:
        agent = await setup()
    return agent

# Define the async function for Gradio to process prompts with persistent memory
async def process_prompt(user_input):
    try:
        # Ensure agent is initialized
        current_agent = await init_agent()
        
        # Get or create session ID
        session_id = session_manager.get_current_session()
        if session_id is None:
            session_id = session_manager.start_new_session()
        
        # Prepare the configuration for the agent with thread_id for persistence
        config = {
            "configurable": {
                "thread_id": session_id  # This ensures state persistence across calls
            }
        }
        
        # Create the query with system prompt
        query = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        }
        
        logger.info(f"Processing user input in session {session_id[:8]}...: {user_input[:100]}...")
        
        # Invoke the agent with config - MemorySaver automatically handles state persistence
        response = await current_agent.ainvoke(query, config=config)
        print(f"Response received: {response}")
        
        # Extract the response content
        response_text = ""
        if 'messages' in response and isinstance(response['messages'], list):
            # Get all assistant messages for full context
            assistant_messages = []
            for msg in response['messages']:
                if hasattr(msg, 'content') and msg.content:
                    if hasattr(msg, 'type') and msg.type == 'ai':
                        assistant_messages.append(msg.content)
                    elif not hasattr(msg, 'type'):  # Fallback for messages without type
                        assistant_messages.append(str(msg.content))
            
            if assistant_messages:
                response_text = "\n\n".join(assistant_messages)
            else:
                # Fallback: get the last message content
                last_message = response['messages'][-1]
                if hasattr(last_message, 'content'):
                    response_text = last_message.content
                else:
                    response_text = str(last_message)
        else:
            response_text = str(response)
        
        # Add session info to response
        session_status = f"\n\n🧠 **Session ID:** {session_id[:8]}... (State automatically saved)"
        response_text += session_status
        
        logger.info(f"Response processed and state saved for session {session_id[:8]}...")
        return response_text
            
    except Exception as e:
        logger.error(f"Error processing prompt: {e}")
        return f"Error: {e}\n\nPlease check that:\n1. The Gradio MCP server is running on port 7860\n2. Your Google API key is set correctly\n3. The server is accessible"

def start_new_project():
    """Start a new website project (new session)"""
    session_id = session_manager.start_new_session()
    return f"🚀 **Started New Website Project!**\n\nSession ID: {session_id[:8]}...\n\nYou can now create a fresh website. Previous conversations are saved separately."

def get_session_info():
    """Get current session information"""
    session_id = session_manager.get_current_session()
    if session_id is None:
        return "📭 No active session. Start a new project or send a message to begin."
    
    # Try to get conversation history from memory_saver
    try:
        config = {"configurable": {"thread_id": session_id}}
        # Note: In a real implementation, you might want to add a method to retrieve conversation history
        return f"📊 **Active Session:** {session_id[:8]}...\n\nState is automatically managed by LangGraph MemorySaver.\nAll your conversation history and modifications are preserved!"
    except Exception as e:
        return f"📊 **Active Session:** {session_id[:8]}...\n\nMemory checkpointer is active and managing state automatically."

def clear_current_session():
    """Clear the current session and start fresh"""
    old_session = session_manager.get_current_session()
    new_session = session_manager.start_new_session()
    
    return f"🧹 **Session Cleared!**\n\nOld session: {old_session[:8] if old_session else 'None'}...\nNew session: {new_session[:8]}...\n\nStarting fresh - previous state is preserved in memory but no longer active."

# Create the Gradio interface with session management
def create_interface():
    with gr.Blocks(theme=gr.themes.Soft(), title="🌐 Website Assistant with LangGraph Memory") as iface:
        gr.Markdown("""
        # 🌐 Website Creation Assistant with LangGraph MemorySaver
        
        This assistant uses **LangGraph's MemorySaver** for automatic state persistence!
        
        ✨ **Features:**
        - **Automatic Memory**: State saved after each interaction
        - **Seamless Modifications**: "Change the circle to blue" works perfectly
        - **Session Management**: Each project has its own conversation thread
        - **Zero Configuration**: Memory just works!
        
        **Examples:**
        - "Create a landing page with a hero section"
        - "Make the background gradient from blue to purple" 
        - "Add a contact form with glassmorphism effect"
        - "Change the font to something more modern"
        """)
        
        with gr.Row():
            with gr.Column(scale=4):
                user_input = gr.Textbox(
                    lines=3,
                    placeholder="Describe your website or modifications...\nExample: 'Create a portfolio site' or 'Make the header sticky'",
                    label="Your Request"
                )
                
                with gr.Row():
                    submit_btn = gr.Button("🚀 Create/Modify Website", variant="primary", scale=2)
                    new_project_btn = gr.Button("📝 New Project", variant="secondary")
                    session_info_btn = gr.Button("📊 Session Info", variant="secondary")
                    clear_session_btn = gr.Button("🧹 Clear Session", variant="secondary")
                
            with gr.Column(scale=1):
                gr.Markdown("""
                ### 🧠 LangGraph Memory:
                - **Auto-saves** after each step
                - **Persistent** conversation state
                - **Thread-based** session management
                - **Zero-config** memory
                
                ### 💡 Memory Benefits:
                - Say "change it to blue" - it remembers!
                - Build incrementally on previous work
                - No manual state management needed
                - Automatic conversation context
                """)
        
        output = gr.Textbox(
            lines=15,
            label="Response",
            show_copy_button=True
        )
        
        # Event handlers
        submit_btn.click(
            fn=process_prompt,
            inputs=user_input,
            outputs=output
        )
        
        new_project_btn.click(
            fn=start_new_project,
            outputs=output
        )
        
        session_info_btn.click(
            fn=get_session_info,
            outputs=output
        )
        
        clear_session_btn.click(
            fn=clear_current_session,
            outputs=output
        )
        
        # Examples with progressive modifications
        gr.Examples(
            examples=[
                "Create a modern landing page with hero section",
                "Add a navigation bar with glassmorphism effect",
                "Change the hero background to a gradient",
                "Make the text larger and add a call-to-action button",
                "Add a features section below the hero",
                "Change the color scheme to dark mode",
                "Deploy the website to Netlify"
            ],
            inputs=user_input,
            label="Try these progressive examples (each builds on the previous):"
        )
        
        gr.Markdown("""
        ### 🔧 How LangGraph MemorySaver Works:
        
        1. **Automatic Checkpointing**: Every step is saved automatically
        2. **Thread-Based Sessions**: Each conversation has a unique thread ID
        3. **State Persistence**: Full conversation context is maintained
        4. **Seamless Modifications**: Agent remembers previous code and builds upon it
        5. **No Manual Management**: Memory "just works" - no need to manually store/retrieve state
        
        **Perfect for iterative website development!** 🎨
        """)
    
    return iface

# Launch the Gradio app
if __name__ == "__main__":
    try:
        # Test the setup first
        print("Testing MCP connection and initializing MemorySaver...")
        asyncio.run(init_agent())
        print("✅ MCP connection successful!")
        print("✅ LangGraph MemorySaver initialized!")
        
        # Create and launch interface
        iface = create_interface()
        iface.launch()
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure your Gradio MCP server is running on port 7860")
        print("2. Check your GOOGLE_API_KEY environment variable")
        print("3. Verify the MCP server is accessible")
        print("4. Ensure LangGraph is installed: pip install langgraph")
