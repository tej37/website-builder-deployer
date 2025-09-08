import gradio as gr
import subprocess
import shlex
from subprocess import check_output
import re
import os
import json
import base64
from pathlib import Path
from typing import Dict, List, Optional
import mimetypes

def remove_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def run_command(command):
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
        stdout, stderr = process.communicate()
        return (stdout or "") + (stderr or "")
    except Exception as e:
        return str(e)

# ============================================================================
# MCP RESOURCES - Image Management
# ============================================================================

# Define the images directory
IMAGES_DIR = r"C:\Users\tej\Desktop\website_final_version1"
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.bmp', '.ico'}

def get_available_images():
    """
    Get a list of all available images in the resources directory.
    Returns:
        dict: Dictionary with image names as keys and their info as values
    """
    images_info = {}
    
    try:
        if not os.path.exists(IMAGES_DIR):
            os.makedirs(IMAGES_DIR, exist_ok=True)
            return {"message": f"Images directory created at: {IMAGES_DIR}. Please add some images."}
        
        for file_path in Path(IMAGES_DIR).iterdir():
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_IMAGE_FORMATS:
                file_size = file_path.stat().st_size
                images_info[file_path.name] = {
                    "name": file_path.name,
                    "path": str(file_path),
                    "size": f"{file_size / 1024:.1f} KB",
                    "format": file_path.suffix.lower(),
                    "mime_type": mimetypes.guess_type(str(file_path))[0] or "image/unknown"
                }
        
        if not images_info:
            return {"message": "No supported image files found. Please add images to the directory."}
            
        return images_info
        
    except Exception as e:
        return {"error": f"Failed to scan images directory: {str(e)}"}

def list_available_images():
    """
    MCP Resource: List all available images with their details.
    Returns:
        str: JSON formatted list of available images
    """
    images_info = get_available_images()
    
    if "message" in images_info or "error" in images_info:
        return json.dumps(images_info, indent=2)
    
    # Format for easy reading
    result = {
        "available_images": images_info,
        "total_images": len(images_info),
        "supported_formats": list(SUPPORTED_IMAGE_FORMATS),
        "images_directory": IMAGES_DIR
    }
    
    return json.dumps(result, indent=2)

def get_image_info(image_name: str):
    """
    MCP Resource: Get detailed information about a specific image.
    Args:
        image_name (str): Name of the image file
    Returns:
        str: JSON formatted image information
    """
    images_info = get_available_images()
    
    if "message" in images_info or "error" in images_info:
        return json.dumps(images_info, indent=2)
    
    if image_name not in images_info:
        available = list(images_info.keys())
        return json.dumps({
            "error": f"Image '{image_name}' not found.",
            "available_images": available
        }, indent=2)
    
    image_info = images_info[image_name]
    
    # Add relative path for HTML usage
    image_info["relative_path"] = image_name  # Since images are in the same directory as HTML
    image_info["html_usage"] = f'<img src="{image_name}" alt="{Path(image_name).stem}">'
    
    return json.dumps(image_info, indent=2)

def copy_image_to_website(image_name: str, new_name: str = None):
    """
    MCP Tool: Copy an image from resources to the website directory (if not already there).
    Args:
        image_name (str): Name of the source image
        new_name (str): Optional new name for the image (default: keep original name)
    Returns:
        str: Success or error message with HTML usage example
    """
    try:
        images_info = get_available_images()
        
        if "message" in images_info or "error" in images_info:
            return json.dumps(images_info, indent=2)
        
        if image_name not in images_info:
            available = list(images_info.keys())
            return f"❌ Image '{image_name}' not found.\nAvailable images: {', '.join(available)}"
        
        source_path = Path(images_info[image_name]["path"])
        destination_name = new_name if new_name else image_name
        destination_path = Path(IMAGES_DIR) / destination_name
        
        # If it's already in the website directory, just confirm
        if source_path == destination_path:
            return f"✅ Image '{image_name}' is already in the website directory.\n\nHTML usage: <img src=\"{destination_name}\" alt=\"{Path(destination_name).stem}\">\n\nPath: {destination_path}"
        
        # Copy the file if different location
        import shutil
        shutil.copy2(source_path, destination_path)
        
        return f"✅ Image copied successfully!\n\nSource: {source_path}\nDestination: {destination_path}\n\nHTML usage: <img src=\"{destination_name}\" alt=\"{Path(destination_name).stem}\">"
        
    except Exception as e:
        return f"❌ Failed to copy image: {str(e)}"

def generate_image_gallery_html():
    """
    MCP Tool: Generate HTML code for displaying all available images in a gallery.
    Returns:
        str: HTML code for an image gallery
    """
    try:
        images_info = get_available_images()
        
        if "message" in images_info or "error" in images_info:
            return json.dumps(images_info, indent=2)
        
        if not images_info:
            return "<!-- No images available for gallery -->"
        
        gallery_html = """
<!-- Image Gallery -->
<div class="image-gallery" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; padding: 20px;">
"""
        
        for image_name, info in images_info.items():
            gallery_html += f"""
    <div class="gallery-item" style="text-align: center; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
        <img src="{image_name}" alt="{Path(image_name).stem}" style="max-width: 100%; height: 150px; object-fit: cover; border-radius: 4px;">
        <p style="margin-top: 10px; font-size: 14px; color: #666;">{image_name}</p>
        <small style="color: #999;">{info['size']}</small>
    </div>
"""
        
        gallery_html += """
</div>
<!-- End Image Gallery -->
"""
        
        return gallery_html.strip()
        
    except Exception as e:
        return f"<!-- Error generating gallery: {str(e)} -->"

def suggest_image_usage(website_context: str):
    """
    MCP Tool: Suggest which images to use based on website context.
    Args:
        website_context (str): Description of the website being built
    Returns:
        str: JSON with image suggestions
    """
    try:
        images_info = get_available_images()
        
        if "message" in images_info or "error" in images_info:
            return json.dumps(images_info, indent=2)
        
        suggestions = []
        context_lower = website_context.lower()
        
        for image_name, info in images_info.items():
            image_name_lower = image_name.lower()
            suggestion = {
                "image": image_name,
                "suggested_usage": "",
                "html_example": f'<img src="{image_name}" alt="{Path(image_name).stem}">',
                "confidence": "medium"
            }
            
            # Smart suggestions based on image names and context
            if "logo" in image_name_lower:
                suggestion["suggested_usage"] = "Use as website logo in header"
                suggestion["html_example"] = f'<img src="{image_name}" alt="Company Logo" class="logo" style="height: 50px;">'
                suggestion["confidence"] = "high"
            elif "hero" in image_name_lower or "banner" in image_name_lower:
                suggestion["suggested_usage"] = "Use as hero/banner background image"
                suggestion["html_example"] = f'<div style="background-image: url(\'{image_name}\'); background-size: cover; background-position: center;"></div>'
                suggestion["confidence"] = "high"
            elif "product" in image_name_lower:
                suggestion["suggested_usage"] = "Use in product showcase or gallery"
                suggestion["html_example"] = f'<img src="{image_name}" alt="Product" class="product-image" style="max-width: 300px;">'
                suggestion["confidence"] = "high"
            elif "team" in image_name_lower or "staff" in image_name_lower:
                suggestion["suggested_usage"] = "Use in team/about section"
                suggestion["html_example"] = f'<img src="{image_name}" alt="Team Member" class="team-photo" style="border-radius: 50%; width: 150px;">'
                suggestion["confidence"] = "high"
            elif "icon" in image_name_lower:
                suggestion["suggested_usage"] = "Use as icon or small decorative element"
                suggestion["html_example"] = f'<img src="{image_name}" alt="Icon" style="width: 32px; height: 32px;">'
                suggestion["confidence"] = "medium"
            
            # Context-based suggestions
            if "portfolio" in context_lower and any(word in image_name_lower for word in ["work", "project", "portfolio"]):
                suggestion["suggested_usage"] = "Perfect for portfolio showcase"
                suggestion["confidence"] = "high"
            elif "landing" in context_lower and "hero" in image_name_lower:
                suggestion["suggested_usage"] = "Ideal for landing page hero section"
                suggestion["confidence"] = "high"
            
            suggestions.append(suggestion)
        
        result = {
            "website_context": website_context,
            "total_images": len(images_info),
            "suggestions": suggestions
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Failed to generate suggestions: {str(e)}"}, indent=2)

# ============================================================================
# EXISTING TOOLS (Enhanced with image integration)
# ============================================================================

# Tool 1: Check if Netlify CLI is installed
def check_netlify_cli():
    """
    Check if Netlify CLI is installed.
    Returns:
        str: The output of the 'netlify' command. if not installed, return an error message.
    """
    result = run_command("netlify")
    if "'netlify' n'est pas reconnu" in result or "'netlify' is not recognized" in result:
        return "Netlify CLI is NOT installed."
    else:
        return "Netlify CLI is installed.\n\n" + result

# Tool 2: Install Netlify CLI
def install_netlify_cli():
    """
    Install Netlify CLI if not already installed.
    Returns:
        str: The output of the 'npm install -g netlify-cli' command.
    """
    result = run_command("netlify")
    if "'netlify' n'est pas reconnu" in result or "'netlify' is not recognized" in result:
        return run_command("npm install -g netlify-cli")

# Tool 3: Login to Netlify
def login_netlify():
    """
    Login to Netlify.
    Returns:
        str: The output of the 'netlify login' command.
    """
    return run_command("netlify login")

def go_to_project_folder_for_deployment():
    """
    Change the working directory of the current Python process to the folder that contains website files for deployment.
    """
    try:
        os.chdir(IMAGES_DIR)  # Use the same directory as images
        return f"✅ Changed working directory to: {os.getcwd()}"
    except Exception as e:
        return f"❌ Failed to change directory: {str(e)}"

# Tool 5: Deploy site (and get URL)
def deploy_netlify():
    """
    Deploy the site to Netlify and extract the URL using JSON output.
    """
    raw_output = run_command("netlify deploy --json")
    clean_output = remove_ansi(raw_output)

    # Try to extract the URL from the JSON output
    match = re.search(r'"deploy_url"\s*:\s*"([^"]+)"', clean_output)
    if match:
        return f"✅ Deploy successful!\n\nURL: {match.group(1)}"
    
    return f"⚠️ Could not find deploy URL.\n\nFull output:\n{clean_output}"

# Tool 6: Helper functions to extract HTML and CSS from Markdown code blocks
def extract_code_blocks(text, lang):
    """
    Extract code blocks of a specific language from Markdown text.
    Args:
        text (str): The Markdown text containing code blocks, the response.text of the llm.
        lang (str): The programming language of the code blocks to extract. 
    Returns:
        str: The extracted code block as a string, or an empty string if not found.
    """
    if not text:
        return "no text provided"
    lang = lang.lower()
    # Use a regex pattern to match code blocks with the specified language
    pattern = fr"```{lang}\s+(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""

def save_code_to_path(the_extracted_code_blocks, name_of_the_file):
    """
    Save the extracted code block to a file in the website directory.
    Args:
       the_extracted_code_blocks (str): the language code extracted from markdown text.
       name_of_the_file (str): the name of the file to save (e.g., "index.html", "style.css")
    Returns:
       str: a message indicating if the file was successfully saved
    """
    # Create directory if it doesn't exist
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Save the file to the specified path
    file_path = os.path.join(IMAGES_DIR, name_of_the_file)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(the_extracted_code_blocks)
    
    # Also show available images for reference
    images_info = get_available_images()
    available_images = list(images_info.keys()) if isinstance(images_info, dict) and "error" not in images_info and "message" not in images_info else []
    
    result = f"✅ Website file saved successfully: {file_path}"
    if available_images:
        result += f"\n\n📸 Available images in directory: {', '.join(available_images)}"
        result += f"\n💡 You can reference these images in your HTML using: <img src=\"image_name.ext\" alt=\"description\">"
    
    return result

def display_the_website():
    """
    Display the website in the default web browser.
    """
    try:
        # Open the index.html file in the default web browser
        index_path = os.path.join(IMAGES_DIR, "index.html")
        os.startfile(index_path)
        return "✅ Website opened successfully in the default web browser."
    except Exception as e:
        return f"❌ Failed to open website: {str(e)}"

# ============================================================================
# GRADIO INTERFACE WITH IMAGE RESOURCES
# ============================================================================

# Gradio Interface with new image resource tools
demo = gr.TabbedInterface(
    [
        # Existing tools
        gr.Interface(check_netlify_cli, None, gr.Textbox(label="Output", lines=10), api_name="check_netlify_cli", title="Check Netlify CLI"),
        gr.Interface(install_netlify_cli, None, gr.Textbox(label="Output", lines=10), api_name="install_netlify_cli", title="Install Netlify CLI"),
        gr.Interface(login_netlify, None, gr.Textbox(label="Output", lines=10), api_name="login_netlify", title="Login to Netlify"),
        gr.Interface(deploy_netlify, None, gr.Textbox(label="Output", lines=10), api_name="deploy_netlify", title="Deploy Site"),
        gr.Interface(extract_code_blocks, [gr.Textbox(label="Markdown Text"), gr.Textbox(label="Language (e.g., html, css)")], gr.Textbox(label="Extracted Code"), api_name="extract_code_blocks", title="Extract Code Blocks"),
        gr.Interface(save_code_to_path, [gr.Textbox(label="Code"), gr.Textbox(label="Name of the file")], gr.Textbox(label="Output Message"), api_name="save_code_to_path", title="Save Code to Path"),
        gr.Interface(display_the_website, None, gr.Textbox(label="Output", lines=10), api_name="display_the_website", title="Display Website"),
        gr.Interface(go_to_project_folder_for_deployment, None, gr.Textbox(label="Output", lines=10), api_name="go_to_project_folder_for_deployment", title="Go to Project Folder"),
        
        # New Image Resource tools
        gr.Interface(list_available_images, None, gr.Textbox(label="Available Images (JSON)", lines=15), api_name="list_available_images", title="📸 List Available Images"),
        gr.Interface(get_image_info, gr.Textbox(label="Image Name (e.g., logo.png)"), gr.Textbox(label="Image Info (JSON)", lines=10), api_name="get_image_info", title="🔍 Get Image Info"),
        gr.Interface(copy_image_to_website, [gr.Textbox(label="Image Name"), gr.Textbox(label="New Name (optional)", placeholder="Leave empty to keep original name")], gr.Textbox(label="Result", lines=5), api_name="copy_image_to_website", title="📁 Copy Image to Website"),
        gr.Interface(generate_image_gallery_html, None, gr.Textbox(label="Gallery HTML Code", lines=15), api_name="generate_image_gallery_html", title="🖼️ Generate Image Gallery HTML"),
        gr.Interface(suggest_image_usage, gr.Textbox(label="Website Context (e.g., 'portfolio website', 'landing page')"), gr.Textbox(label="Image Usage Suggestions (JSON)", lines=15), api_name="suggest_image_usage", title="💡 Suggest Image Usage"),
    ],
    [
        "Check CLI",
        "Install CLI",
        "Login",
        "Deploy",
        "Extract Code",
        "Save Code",
        "Display Website",
        "Go to Project Folder",
        "📸 List Images",
        "🔍 Image Info",
        "📁 Copy Image",
        "🖼️ Gallery HTML",
        "💡 Suggest Usage"
    ]
)

if __name__ == "__main__":
    # Create images directory if it doesn't exist
    os.makedirs(IMAGES_DIR, exist_ok=True)
    print(f"📸 Images directory: {IMAGES_DIR}")
    print(f"🎯 Supported formats: {', '.join(SUPPORTED_IMAGE_FORMATS)}")
    print("🚀 Starting MCP Server with Image Resources...")
    
    demo.launch(mcp_server=True)
