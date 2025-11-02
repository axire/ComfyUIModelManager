import os
import json
import datetime
import sys
import subprocess
import struct
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# SafeTensor Inspector functionality
# We use manual header parsing to avoid the heavy torch/numpy dependencies
SAFETENSORS_AVAILABLE = True

def _read_safetensor_header(file_path):
    """
    Read safetensor file header using only Python stdlib (no torch/numpy needed).
    Returns (metadata_dict, tensor_keys_list) or raises exception on error.
    """
    try:
        with open(file_path, 'rb') as f:
            # Read first 8 bytes to get header length
            header_size_bytes = f.read(8)
            if len(header_size_bytes) < 8:
                raise ValueError("File too small to be a valid safetensors file")

            # Unpack as little-endian unsigned 64-bit integer
            header_length = struct.unpack('<Q', header_size_bytes)[0]

            # Read the JSON header
            header_data = f.read(header_length)
            if len(header_data) < header_length:
                raise ValueError("Incomplete header data")

            # Parse JSON header
            header = json.loads(header_data.decode('utf-8'))

            # Extract metadata (stored in special __metadata__ key)
            metadata = header.get('__metadata__', {})

            # Extract tensor keys (all keys except __metadata__)
            tensor_keys = [k for k in header.keys() if k != '__metadata__']

            return metadata, tensor_keys

    except Exception as e:
        raise Exception(f"Failed to read safetensor header: {str(e)}")

# Configuration file for storing repositories and installations
CONFIG_FILE = "model_manager_config.json"

class ModelManagerConfig:
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.load_config()
    
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
                self.data = self.get_default_config()
        else:
            self.data = self.get_default_config()
    
    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_default_config(self):
        return {
            "repositories": [
                {
                    "id": 1,
                    "name": "Default Resources",
                    "path": "/mnt/nvme0n1p1/ai/resources",
                    "description": "Default model repository",
                    "created": datetime.datetime.now().isoformat(),
                    "exists": os.path.exists("/mnt/nvme0n1p1/ai/resources")
                }
            ],
            "comfyui_installations": [
                {
                    "id": 1,
                    "name": "Default ComfyUI",
                    "path": "/home/daniel/ai/comfy1/ComfyUI",
                    "description": "Default ComfyUI installation",
                    "created": datetime.datetime.now().isoformat(),
                    "exists": os.path.exists("/home/daniel/ai/comfy1/ComfyUI")
                }
            ],
            "links": {},
            "link_status": {},
            "folder_snapshots": {},
            "enabled_custom_folders": {}  # repo_id -> [list of enabled custom folder names]
        }
    
    def add_repository(self, name, path, description=""):
        repo = {
            "id": len(self.data["repositories"]) + 1,
            "name": name,
            "path": os.path.abspath(path),
            "description": description,
            "created": datetime.datetime.now().isoformat(),
            "exists": os.path.exists(path)
        }
        self.data["repositories"].append(repo)
        return repo
    
    def add_comfyui_installation(self, name, path, description=""):
        installation = {
            "id": len(self.data["comfyui_installations"]) + 1,
            "name": name,
            "path": os.path.abspath(path),
            "description": description,
            "created": datetime.datetime.now().isoformat(),
            "exists": os.path.exists(path)
        }
        self.data["comfyui_installations"].append(installation)
        return installation
    
    def update_repository(self, repo_id, name=None, path=None, description=None):
        for repo in self.data["repositories"]:
            if repo["id"] == repo_id:
                if name is not None:
                    repo["name"] = name
                if path is not None:
                    repo["path"] = os.path.abspath(path)
                    repo["exists"] = os.path.exists(path)
                if description is not None:
                    repo["description"] = description
                repo["modified"] = datetime.datetime.now().isoformat()
                return repo
        return None
    
    def update_comfyui_installation(self, install_id, name=None, path=None, description=None):
        for install in self.data["comfyui_installations"]:
            if install["id"] == install_id:
                if name is not None:
                    install["name"] = name
                if path is not None:
                    install["path"] = os.path.abspath(path)
                    install["exists"] = os.path.exists(path)
                if description is not None:
                    install["description"] = description
                install["modified"] = datetime.datetime.now().isoformat()
                return install
        return None
    
    def delete_repository(self, repo_id):
        self.data["repositories"] = [r for r in self.data["repositories"] if r["id"] != repo_id]
        # Clean up links
        for install_id in list(self.data["links"].keys()):
            self.data["links"][install_id] = [r for r in self.data["links"][install_id] if r != repo_id]
    
    def delete_comfyui_installation(self, install_id):
        self.data["comfyui_installations"] = [i for i in self.data["comfyui_installations"] if i["id"] != install_id]
        # Clean up links
        if str(install_id) in self.data["links"]:
            del self.data["links"][str(install_id)]
    
    def check_path_exists(self, path):
        return os.path.exists(path)
    
    def refresh_all_paths(self):
        for repo in self.data["repositories"]:
            repo["exists"] = os.path.exists(repo["path"])
        for install in self.data["comfyui_installations"]:
            install["exists"] = os.path.exists(install["path"])
    
    def update_all_link_status(self, linker):
        """Update link status for all installations"""
        if "link_status" not in self.data:
            self.data["link_status"] = {}
        
        for install in self.data["comfyui_installations"]:
            install_id = str(install["id"])
            self.data["link_status"][install_id] = {}
            
            # Check each linked repository
            linked_repos = self.data["links"].get(install_id, [])
            total_links = 0
            
            for repo_id in linked_repos:
                repo = next((r for r in self.data["repositories"] if r["id"] == repo_id), None)
                if repo:
                    status = linker.get_link_status(repo["path"], install["path"])
                    self.data["link_status"][install_id][str(repo_id)] = status
                    
                    # Count total linked files
                    for folder_status in status.values():
                        total_links += folder_status.get("linked_count", 0)
            
            # Store total count for easy access
            self.data["link_status"][install_id]["_total_links"] = total_links
    
    def get_installation_link_summary(self, install_id):
        """Get a summary of links for an installation"""
        install_key = str(install_id)
        if "link_status" not in self.data or install_key not in self.data["link_status"]:
            return {"total_links": 0, "folders": {}}
        
        status_data = self.data["link_status"][install_key]
        total_links = status_data.get("_total_links", 0)
        
        # Aggregate folder stats across all repositories
        folder_summary = {}
        for key, repo_status in status_data.items():
            if key.startswith("_"):  # Skip metadata keys
                continue
            
            for folder, folder_data in repo_status.items():
                if folder not in folder_summary:
                    folder_summary[folder] = {"linked_count": 0, "src_exists": False, "dest_exists": False}
                
                folder_summary[folder]["linked_count"] += folder_data.get("linked_count", 0)
                folder_summary[folder]["src_exists"] = folder_summary[folder]["src_exists"] or folder_data.get("src_exists", False)
                folder_summary[folder]["dest_exists"] = folder_summary[folder]["dest_exists"] or folder_data.get("dest_exists", False)
        
        return {"total_links": total_links, "folders": folder_summary}
    
    def link_repository_to_installation(self, install_id, repo_id):
        install_key = str(install_id)
        if install_key not in self.data["links"]:
            self.data["links"][install_key] = []
        if repo_id not in self.data["links"][install_key]:
            self.data["links"][install_key].append(repo_id)
            return True
        return False
    
    def unlink_repository_from_installation(self, install_id, repo_id):
        install_key = str(install_id)
        if install_key in self.data["links"] and repo_id in self.data["links"][install_key]:
            self.data["links"][install_key].remove(repo_id)
            return True
        return False
    
    def get_linked_repositories(self, install_id):
        install_key = str(install_id)
        linked_repo_ids = self.data["links"].get(install_key, [])
        return [r for r in self.data["repositories"] if r["id"] in linked_repo_ids]
    
    def get_repository_folders(self, repo_path):
        """Get all model folders within a repository, including non-standard ones"""
        # Official ComfyUI model directories (as of 2024)
        standard_folders = [
            "audio_encoders", "checkpoints", "clip", "clip_vision", "configs",
            "controlnet", "diffusers", "diffusion_models", "embeddings", "gligen",
            "hypernetworks", "loras", "model_patches", "photomaker", "style_models",
            "text_encoders", "unet", "upscale_models", "vae", "vae_approx"
        ]
        all_folders = []
        total_files = 0
        total_size_bytes = 0
        
        if os.path.exists(repo_path):
            # Get all directories in the repository
            try:
                for item in os.listdir(repo_path):
                    item_path = os.path.join(repo_path, item)
                    if os.path.isdir(item_path):
                        # Count files and calculate size in the directory
                        try:
                            folder_files = 0
                            folder_size = 0
                            for f in os.listdir(item_path):
                                file_path = os.path.join(item_path, f)
                                if os.path.isfile(file_path):
                                    folder_files += 1
                                    total_files += 1
                                    try:
                                        file_size = os.path.getsize(file_path)
                                        folder_size += file_size
                                        total_size_bytes += file_size
                                    except (PermissionError, OSError):
                                        pass
                        except (PermissionError, OSError):
                            folder_files = 0
                            folder_size = 0
                        
                        all_folders.append({
                            "name": item,
                            "path": item_path,
                            "file_count": folder_files,
                            "size_bytes": folder_size,
                            "exists": True,
                            "is_standard": item in standard_folders
                        })
                
                # Sort folders: standard folders first, then others alphabetically
                all_folders.sort(key=lambda x: (not x["is_standard"], x["name"]))
                
            except (PermissionError, OSError) as e:
                print(f"Error scanning repository {repo_path}: {e}")
        
        return {
            "folders": all_folders,
            "total_files": total_files,
            "total_size_bytes": total_size_bytes,
            "total_size_gb": round(total_size_bytes / (1024**3), 2) if total_size_bytes > 0 else 0
        }
    
    def detect_repository_changes(self, repo_id):
        """Detect changes in a repository's folder structure"""
        repo = next((r for r in self.data["repositories"] if r["id"] == repo_id), None)
        if not repo or not repo["exists"]:
            return {"new_folders": [], "removed_folders": [], "changed_folders": []}
        
        # Get current folder state
        current_folders = self.get_repository_folders(repo["path"])
        
        # Get previous folder state from config
        if "folder_snapshots" not in self.data:
            self.data["folder_snapshots"] = {}
        
        repo_key = str(repo_id)
        previous_folders = self.data["folder_snapshots"].get(repo_key, [])
        
        # Convert to sets for comparison
        current_names = {f["name"] for f in current_folders["folders"]}
        previous_names = {f["name"] for f in previous_folders}
        
        # Find changes
        new_folders = [f for f in current_folders["folders"] if f["name"] in (current_names - previous_names)]
        removed_folders = [{"name": name} for name in (previous_names - current_names)]
        
        # Find folders with changed file counts
        changed_folders = []
        current_dict = {f["name"]: f for f in current_folders["folders"]}
        previous_dict = {f["name"]: f for f in previous_folders}
        
        for name in (current_names & previous_names):
            current_count = current_dict[name]["file_count"]
            previous_count = previous_dict[name]["file_count"]
            if current_count != previous_count:
                changed_folders.append({
                    "name": name,
                    "previous_count": previous_count,
                    "current_count": current_count,
                    "change": current_count - previous_count
                })
        
        # Update snapshot
        self.data["folder_snapshots"][repo_key] = current_folders["folders"]
        
        return {
            "new_folders": new_folders,
            "removed_folders": removed_folders,
            "changed_folders": changed_folders
        }
    
    def check_all_repositories_for_changes(self):
        """Check all repositories for changes and return summary"""
        changes_summary = {}
        total_changes = 0
        
        for repo in self.data["repositories"]:
            if repo["exists"]:
                changes = self.detect_repository_changes(repo["id"])
                if changes["new_folders"] or changes["removed_folders"] or changes["changed_folders"]:
                    changes_summary[repo["id"]] = {
                        "repo_name": repo["name"],
                        "changes": changes
                    }
                    total_changes += len(changes["new_folders"]) + len(changes["removed_folders"]) + len(changes["changed_folders"])
        
        return {"repositories": changes_summary, "total_changes": total_changes}

    def toggle_custom_folder(self, repo_id, folder_name):
        """Toggle a custom folder for a repository"""
        if "enabled_custom_folders" not in self.data:
            self.data["enabled_custom_folders"] = {}

        repo_key = str(repo_id)
        if repo_key not in self.data["enabled_custom_folders"]:
            self.data["enabled_custom_folders"][repo_key] = []

        if folder_name in self.data["enabled_custom_folders"][repo_key]:
            self.data["enabled_custom_folders"][repo_key].remove(folder_name)
            enabled = False
        else:
            self.data["enabled_custom_folders"][repo_key].append(folder_name)
            enabled = True

        return enabled

    def get_enabled_custom_folders(self, repo_id):
        """Get list of enabled custom folders for a repository"""
        if "enabled_custom_folders" not in self.data:
            self.data["enabled_custom_folders"] = {}

        repo_key = str(repo_id)
        return self.data["enabled_custom_folders"].get(repo_key, [])

class ModelLinker:
    """Handles the actual symbolic linking between repositories and ComfyUI installations"""

    def __init__(self):
        # Official ComfyUI model directories (as of 2024)
        self.standard_folders = [
            "audio_encoders",
            "checkpoints",
            "clip",
            "clip_vision",
            "configs",
            "controlnet",
            "diffusers",
            "diffusion_models",
            "embeddings",
            "gligen",
            "hypernetworks",
            "loras",
            "model_patches",
            "photomaker",
            "style_models",
            "text_encoders",
            "unet",
            "upscale_models",
            "vae",
            "vae_approx"
        ]
    
    def link_repository_to_installation(self, repo_path, install_path, repo_id=None, config=None):
        """Link all model folders from repository to ComfyUI installation"""
        results = {}
        models_path = os.path.join(install_path, "models")

        if not os.path.exists(models_path):
            os.makedirs(models_path, exist_ok=True)

        # Get enabled custom folders if config is provided
        custom_folders = []
        if config and repo_id:
            custom_folders = config.get_enabled_custom_folders(repo_id)

        # Link standard folders
        for folder in self.standard_folders:
            src_folder = os.path.join(repo_path, folder)
            dest_folder = os.path.join(models_path, folder)

            if os.path.exists(src_folder):
                results[folder] = self._link_folder(src_folder, dest_folder, folder)
            else:
                results[folder] = {"success": False, "message": f"Source folder {src_folder} does not exist", "count": 0}

        # Link enabled custom folders
        for folder in custom_folders:
            src_folder = os.path.join(repo_path, folder)
            dest_folder = os.path.join(models_path, folder)

            if os.path.exists(src_folder):
                results[folder] = self._link_folder(src_folder, dest_folder, folder)
            else:
                results[folder] = {"success": False, "message": f"Custom folder {src_folder} does not exist", "count": 0}

        return results
    
    def unlink_repository_from_installation(self, repo_path, install_path, repo_id=None, config=None):
        """Remove symbolic links for a specific repository from ComfyUI installation"""
        results = {}
        models_path = os.path.join(install_path, "models")

        # Get enabled custom folders if config is provided
        custom_folders = []
        if config and repo_id:
            custom_folders = config.get_enabled_custom_folders(repo_id)
            print(f"DEBUG: Unlinking repo_id={repo_id}, custom_folders={custom_folders}")

        # Unlink standard folders
        for folder in self.standard_folders:
            src_folder = os.path.join(repo_path, folder)
            dest_folder = os.path.join(models_path, folder)
            if os.path.exists(dest_folder):
                results[folder] = self._unlink_folder_for_repository(src_folder, dest_folder, folder)
            else:
                results[folder] = {"success": True, "message": f"Folder {dest_folder} does not exist", "count": 0}

        # Unlink enabled custom folders
        for folder in custom_folders:
            src_folder = os.path.join(repo_path, folder)
            dest_folder = os.path.join(models_path, folder)
            if os.path.exists(dest_folder):
                results[folder] = self._unlink_folder_for_repository(src_folder, dest_folder, folder)
            else:
                results[folder] = {"success": True, "message": f"Custom folder {dest_folder} does not exist", "count": 0}

        return results
    
    def _link_folder(self, src, dest, folder_name):
        """Link ALL files from source to destination folder (not just safetensors)"""
        try:
            if not os.path.exists(src):
                return {"success": False, "message": f"Source directory {src} does not exist", "count": 0}
            
            # Create destination directory if it doesn't exist
            os.makedirs(dest, exist_ok=True)
            
            count = 0
            
            if folder_name in ["loras", "checkpoints"]:
                # For loras and checkpoints, link ALL files recursively
                for root, dirs, files in os.walk(src):
                    for file in files:
                        src_file = os.path.join(root, file)
                        # Calculate relative path from src
                        rel_path = os.path.relpath(src_file, src)
                        dest_file = os.path.join(dest, rel_path)
                        
                        # Create destination directory if needed
                        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                        
                        # Create symbolic link (force overwrite if exists)
                        if os.path.exists(dest_file) or os.path.islink(dest_file):
                            os.remove(dest_file)
                        os.symlink(src_file, dest_file)
                        count += 1
            else:
                # For other folders, link ALL files in the top directory
                for file in os.listdir(src):
                    src_file = os.path.join(src, file)
                    if os.path.isfile(src_file):
                        dest_file = os.path.join(dest, file)
                        
                        # Create symbolic link (force overwrite if exists)
                        if os.path.exists(dest_file) or os.path.islink(dest_file):
                            os.remove(dest_file)
                        os.symlink(src_file, dest_file)
                        count += 1
            
            return {"success": True, "message": f"Linked {count} files", "count": count}
            
        except Exception as e:
            return {"success": False, "message": f"Error linking folder: {str(e)}", "count": 0}
    
    def _unlink_folder_for_repository(self, src_folder, dest_folder, folder_name):
        """Remove only symbolic links that point to files in the specific source repository"""
        try:
            if not os.path.exists(dest_folder):
                return {"success": True, "message": f"Directory {dest_folder} does not exist", "count": 0}

            count = 0
            src_realpath = os.path.realpath(src_folder)
            print(f"DEBUG: Unlinking {folder_name}: src={src_realpath}, dest={dest_folder}")
            
            # Find and remove symbolic links that point to this specific repository
            for root, dirs, files in os.walk(dest_folder, topdown=False):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.islink(file_path):
                        try:
                            # Get the target of the symbolic link
                            link_target = os.path.realpath(file_path)
                            # Check if this link points to our source repository
                            if link_target.startswith(src_realpath):
                                print(f"DEBUG: Removing symlink {file_path} -> {link_target}")
                                os.remove(file_path)
                                count += 1
                        except (OSError, FileNotFoundError):
                            # Link might be broken, remove it anyway if it was targeting our repo
                            try:
                                link_target = os.readlink(file_path)
                                if os.path.abspath(link_target).startswith(src_realpath):
                                    os.remove(file_path)
                                    count += 1
                            except (OSError, FileNotFoundError):
                                pass
                
                # Remove empty directories that we created
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):  # Directory is empty
                            os.rmdir(dir_path)
                    except OSError:
                        pass  # Directory not empty or other error
            
            print(f"DEBUG: Finished unlinking {folder_name}: removed {count} links")
            return {"success": True, "message": f"Removed {count} symbolic links for this repository", "count": count}
            
        except Exception as e:
            return {"success": False, "message": f"Error unlinking folder: {str(e)}", "count": 0}
    
    def _unlink_folder(self, dest):
        """Remove ALL symbolic links from destination folder (used for complete cleanup)"""
        try:
            if not os.path.exists(dest):
                return {"success": True, "message": f"Directory {dest} does not exist", "count": 0}
            
            count = 0
            
            # Find and remove all symbolic links recursively
            for root, dirs, files in os.walk(dest, topdown=False):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.islink(file_path):
                        os.remove(file_path)
                        count += 1
                
                # Remove empty directories
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):  # Directory is empty
                            os.rmdir(dir_path)
                    except OSError:
                        pass  # Directory not empty or other error
            
            return {"success": True, "message": f"Removed {count} symbolic links", "count": count}
            
        except Exception as e:
            return {"success": False, "message": f"Error unlinking folder: {str(e)}", "count": 0}
    
    def get_link_status(self, repo_path, install_path):
        """Check the current link status between repository and installation"""
        results = {}
        models_path = os.path.join(install_path, "models")
        src_realpath = os.path.realpath(repo_path)
        
        for folder in self.standard_folders:
            src_folder = os.path.join(repo_path, folder)
            dest_folder = os.path.join(models_path, folder)
            
            src_exists = os.path.exists(src_folder)
            dest_exists = os.path.exists(dest_folder)
            
            linked_count = 0
            if dest_exists and src_exists:
                # Count symbolic links in destination that point to this specific repository
                for root, dirs, files in os.walk(dest_folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.islink(file_path):
                            try:
                                link_target = os.path.realpath(file_path)
                                if link_target.startswith(src_realpath):
                                    linked_count += 1
                            except (OSError, FileNotFoundError):
                                pass
            
            results[folder] = {
                "src_exists": src_exists,
                "dest_exists": dest_exists,
                "linked_count": linked_count
            }
        
        return results

class ModelManagerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.config = ModelManagerConfig()
        self.linker = ModelLinker()
        # SafeTensor Inspector setup - default to user's home directory for broader access
        self.inspector_root = os.path.expanduser("~")
        super().__init__(*args, **kwargs)
    
    def _send_json_response(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
    
    def _send_html_response(self, html_content):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=UTF-8")
        self.end_headers()
        self.wfile.write(html_content.encode("utf-8"))
    
    def serve_static_file(self, path):
        """Serve static files from the assets directory"""
        try:
            # Remove leading slash and get the file path
            file_path = path.lstrip('/')
            script_dir = os.path.dirname(os.path.abspath(__file__))
            full_path = os.path.join(script_dir, file_path)
            
            # Security check: ensure the path is within the assets directory
            if not os.path.realpath(full_path).startswith(os.path.realpath(os.path.join(script_dir, 'assets'))):
                self.send_error(403, "Forbidden")
                return
            
            if not os.path.exists(full_path):
                self.send_error(404, "File not found")
                return
            
            # Determine content type based on file extension
            _, ext = os.path.splitext(full_path)
            content_types = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.svg': 'image/svg+xml',
                '.css': 'text/css',
                '.js': 'application/javascript',
                '.ico': 'image/x-icon'
            }
            content_type = content_types.get(ext.lower(), 'application/octet-stream')
            
            # Send the file
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "public, max-age=3600")  # Cache for 1 hour
            self.end_headers()
            
            with open(full_path, 'rb') as f:
                self.wfile.write(f.read())
                
        except Exception as e:
            print(f"Error serving static file {path}: {e}")
            self.send_error(500, "Internal server error")
    
    def _get_safetensor_details(self, file_abs_path):
        """Get SafeTensor metadata and tensor keys"""
        if not SAFETENSORS_AVAILABLE:
            return {"error": "safetensors library not installed"}, []
        try:
            metadata, keys = _read_safetensor_header(file_abs_path)
            return metadata, keys
        except Exception as e:
            print(f"Could not read metadata for {file_abs_path}: {e}")
            return {"error": f"Could not read metadata: {str(e)}"}, []
    
    def do_GET(self):
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        if parsed_url.path == "/":
            self.serve_main_interface()
        elif parsed_url.path.startswith("/assets/"):
            # Serve static assets (images, etc.)
            self.serve_static_file(parsed_url.path)
        elif parsed_url.path == "/api/repositories":
            self._send_json_response(self.config.data["repositories"])
        elif parsed_url.path == "/api/installations":
            self._send_json_response(self.config.data["comfyui_installations"])
        elif parsed_url.path == "/api/links":
            self._send_json_response(self.config.data["links"])
        elif parsed_url.path == "/api/config":
            self._send_json_response(self.config.data)
        elif parsed_url.path == "/api/installation_summary":
            install_id = query_params.get('install_id', [None])[0]
            if install_id:
                summary = self.config.get_installation_link_summary(int(install_id))
                self._send_json_response(summary)
            else:
                self.send_error(400, "Missing install_id parameter")
        elif parsed_url.path == "/api/repository_folders":
            repo_id = query_params.get('repo_id', [None])[0]
            if repo_id:
                repo = next((r for r in self.config.data["repositories"] if r["id"] == int(repo_id)), None)
                if repo:
                    folder_data = self.config.get_repository_folders(repo["path"])
                    # Add enabled status for custom folders
                    enabled_custom_folders = self.config.get_enabled_custom_folders(int(repo_id))
                    for folder in folder_data["folders"]:
                        if not folder["is_standard"]:
                            folder["enabled"] = folder["name"] in enabled_custom_folders
                    self._send_json_response(folder_data)
                else:
                    self.send_error(404, "Repository not found")
            else:
                self.send_error(400, "Missing repo_id parameter")
        elif parsed_url.path == "/api/check_path":
            path = query_params.get('path', [None])[0]
            if path:
                exists = self.config.check_path_exists(path)
                self._send_json_response({"path": path, "exists": exists})
            else:
                self.send_error(400, "Missing path parameter")
        elif parsed_url.path == "/api/link_status":
            install_id = query_params.get('install_id', [None])[0]
            repo_id = query_params.get('repo_id', [None])[0]
            if install_id and repo_id:
                install = next((i for i in self.config.data["comfyui_installations"] if i["id"] == int(install_id)), None)
                repo = next((r for r in self.config.data["repositories"] if r["id"] == int(repo_id)), None)
                if install and repo:
                    status = self.linker.get_link_status(repo["path"], install["path"])
                    self._send_json_response(status)
                else:
                    self.send_error(404, "Installation or repository not found")
            else:
                self.send_error(400, "Missing install_id or repo_id parameter")
        elif parsed_url.path.startswith("/inspector"):
            # Redirect to SafeTensor Inspector
            folder_path = query_params.get('path', [None])[0]
            if folder_path:
                # Launch SafeTensor Inspector for this folder
                redirect_url = f"http://localhost:8001/?path={folder_path}"
                self.send_response(302)
                self.send_header("Location", redirect_url)
                self.end_headers()
            else:
                self.send_error(400, "Missing path parameter for inspector")
        elif parsed_url.path == "/api/browse":
            # SafeTensor Inspector browse API (enhanced for path browsing)
            requested_path_param = query_params.get('path', ['.'])[0]
            browse_mode = query_params.get('mode', ['inspector'])[0]  # 'inspector' or 'filesystem'
            
            # Handle empty path as current directory
            if requested_path_param == '.':
                requested_path_param = ''
            
            if browse_mode == 'filesystem':
                # Filesystem browsing mode for path selection
                if requested_path_param == '':
                    # Start from root if no path specified
                    current_browse_abs_path = '/'
                elif requested_path_param == 'HOME':
                    # Special keyword for user home directory
                    current_browse_abs_path = os.path.expanduser('~')
                else:
                    # Handle absolute paths for filesystem browsing
                    if requested_path_param.startswith('/'):
                        current_browse_abs_path = os.path.normpath(requested_path_param)
                    else:
                        # Convert relative to absolute from root
                        current_browse_abs_path = os.path.normpath('/' + requested_path_param)
                
                # Security restrictions for filesystem browsing
                restricted_paths = ['/proc', '/sys', '/dev', '/run', '/tmp/systemd-private']
                if any(current_browse_abs_path.startswith(path) for path in restricted_paths):
                    self.send_error(403, "Access to system directories is restricted")
                    return
                
                # Check if directory exists and is accessible
                if not os.path.isdir(current_browse_abs_path):
                    self.send_error(404, "Directory not found or not accessible")
                    return
                
                browse_results = []
                
                # Add ".." entry for parent directory if not at root
                if current_browse_abs_path != '/':
                    parent_dir = os.path.dirname(current_browse_abs_path)
                    browse_results.append({
                        "name": "..",
                        "type": "directory",
                        "path": parent_dir
                    })
                
                try:
                    # List both directories and files for filesystem browsing
                    for item_name in sorted(os.listdir(current_browse_abs_path)):
                        item_abs_path = os.path.join(current_browse_abs_path, item_name)
                        
                        # Skip hidden files and system directories
                        if item_name.startswith('.') and item_name not in ['..']:
                            continue
                            
                        if os.path.isdir(item_abs_path):
                            # Skip restricted directories
                            if any(item_abs_path.startswith(path) for path in restricted_paths):
                                continue
                                
                            browse_results.append({
                                "name": item_name,
                                "type": "directory",
                                "path": item_abs_path
                            })
                        elif os.path.isfile(item_abs_path):
                            # Add file processing for filesystem mode
                            stat = os.stat(item_abs_path)
                            file_info = {
                                "name": item_name,
                                "type": "file",
                                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                "path": item_abs_path
                            }
                            if item_name.lower().endswith('.safetensors'):
                                if SAFETENSORS_AVAILABLE:
                                    header_meta, tensor_keys = self._get_safetensor_details(item_abs_path)
                                    file_info["header_metadata"] = header_meta
                                    file_info["tensor_keys"] = tensor_keys
                                    # Use enhanced classification
                                    file_info["model_type"] = classify_safetensor(item_name, header_meta, tensor_keys)
                                else:
                                    # Fallback classification without metadata
                                    file_info["model_type"] = classify_safetensor(item_name)
                            elif item_name.lower().endswith(('.ckpt', '.pt', '.bin', '.pth')):
                                file_info["model_type"] = "PyTorch Model/Ckpt"
                            browse_results.append(file_info)
                
                except PermissionError:
                    self.send_error(403, "Permission denied")
                    return
                except Exception as e:
                    print(f"Error listing directory {current_browse_abs_path}: {e}")
                    self.send_error(500, f"Server error: {str(e)}")
                    return
                    
                # Return consistent format with current_path and items
                self._send_json_response({
                    "current_path": current_browse_abs_path,
                    "items": browse_results
                })
                return
            
            else:
                # Original inspector mode (relative to inspector_root)
                current_browse_abs_path = os.path.normpath(os.path.join(self.inspector_root, requested_path_param))
                
                if not os.path.realpath(current_browse_abs_path).startswith(os.path.realpath(self.inspector_root)) or \
                   not os.path.isdir(current_browse_abs_path):
                    self.send_error(403, "Forbidden or invalid path")
                    return

                browse_results = []
                # Add ".." entry for parent directory if not at inspector_root
                if os.path.realpath(current_browse_abs_path) != os.path.realpath(self.inspector_root):
                    parent_dir_abs = os.path.dirname(current_browse_abs_path)
                    parent_dir_rel = os.path.relpath(parent_dir_abs, self.inspector_root)
                    # Ensure relpath doesn't go above inspector_root
                    if not parent_dir_rel.startswith('..'):
                        path_for_parent = parent_dir_rel if parent_dir_rel != '.' else ''

                    browse_results.append({
                        "name": "..",
                        "type": "directory",
                        "path": path_for_parent
                    })
                
                try:
                    for item_name in sorted(os.listdir(current_browse_abs_path)):
                        item_abs_path = os.path.join(current_browse_abs_path, item_name)
                        item_rel_path = os.path.relpath(item_abs_path, self.inspector_root)
                        
                        if os.path.isdir(item_abs_path):
                            browse_results.append({
                                "name": item_name,
                                "type": "directory",
                                "path": item_rel_path
                            })
                        elif os.path.isfile(item_abs_path):
                            stat = os.stat(item_abs_path)
                            file_info = {
                                "name": item_name,
                                "type": "file",
                                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                "path": item_rel_path
                            }
                            if item_name.lower().endswith('.safetensors'):
                                if SAFETENSORS_AVAILABLE:
                                    header_meta, tensor_keys = self._get_safetensor_details(item_abs_path)
                                    file_info["header_metadata"] = header_meta
                                    file_info["tensor_keys"] = tensor_keys
                                    # Use enhanced classification
                                    file_info["model_type"] = classify_safetensor(item_name, header_meta, tensor_keys)
                                else:
                                    # Fallback classification without metadata
                                    file_info["model_type"] = classify_safetensor(item_name)
                            elif item_name.lower().endswith(('.ckpt', '.pt', '.bin', '.pth')):
                                file_info["model_type"] = "PyTorch Model/Ckpt"
                            browse_results.append(file_info)
                except FileNotFoundError:
                    self.send_error(404, "Path not found")
                    return
                except Exception as e:
                    print(f"Error listing directory {current_browse_abs_path}: {e}")
                    self.send_error(500, f"Server error: {str(e)}")
                    return
                self._send_json_response(browse_results)
        elif parsed_url.path == "/api/analyze_file":
            # SafeTensor Inspector analyze API
            requested_file_param = query_params.get('path', [None])[0]
            if not requested_file_param:
                self.send_error(400, "Missing 'path' parameter")
                return

            # Handle both absolute paths (filesystem mode) and relative paths (inspector mode)
            if requested_file_param.startswith('/'):
                # Absolute path - use directly (filesystem mode)
                file_abs_path = os.path.normpath(requested_file_param)
                
                # Apply same security restrictions as filesystem browsing
                restricted_paths = ['/proc', '/sys', '/dev', '/run', '/tmp/systemd-private']
                if any(file_abs_path.startswith(path) for path in restricted_paths):
                    self.send_error(403, "Access to system files is restricted")
                    return
                    
                if not os.path.isfile(file_abs_path):
                    self.send_error(404, "File not found")
                    return
            else:
                # Relative path - use inspector_root (inspector mode)
                file_abs_path = os.path.normpath(os.path.join(self.inspector_root, requested_file_param))

                if not os.path.realpath(file_abs_path).startswith(os.path.realpath(self.inspector_root)) or \
                   not os.path.isfile(file_abs_path):
                    self.send_error(403, "Forbidden or invalid file path")
                    return

            if not file_abs_path.lower().endswith('.safetensors'):
                self.send_error(400, "File is not a .safetensors file or safetensors library unavailable.")
                return
            
            if not SAFETENSORS_AVAILABLE:
                 self._send_json_response({"header_metadata": {"error": "safetensors library not installed"}, "tensor_keys": []}, status_code=200)
                 return

            header_meta, tensor_keys = self._get_safetensor_details(file_abs_path)
            
            # Include enhanced model type in analysis response
            filename = os.path.basename(file_abs_path)
            model_type = classify_safetensor(filename, header_meta, tensor_keys)
            
            self._send_json_response({
                "header_metadata": header_meta, 
                "tensor_keys": tensor_keys,
                "model_type": model_type
            })
        elif parsed_url.path == "/favicon.ico":
            # Simple favicon handler to prevent 404 errors
            self.send_response(204)  # No Content
            self.end_headers()
        else:
            self.send_error(404, "Not found")
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        
        if content_length > 0:
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}
        
        parsed_url = urlparse(self.path)
        
        if parsed_url.path == "/api/repositories":
            repo = self.config.add_repository(
                data.get("name", ""),
                data.get("path", ""),
                data.get("description", "")
            )
            self.config.save_config()
            self._send_json_response(repo, 201)
        elif parsed_url.path == "/api/installations":
            installation = self.config.add_comfyui_installation(
                data.get("name", ""),
                data.get("path", ""),
                data.get("description", "")
            )
            self.config.save_config()
            self._send_json_response(installation, 201)
        elif parsed_url.path == "/api/link":
            install_id = data.get("install_id")
            repo_id = data.get("repo_id")
            if self.config.link_repository_to_installation(install_id, repo_id):
                self.config.save_config()
                self._send_json_response({"success": True})
            else:
                self._send_json_response({"success": False, "error": "Already linked"}, 400)
        elif parsed_url.path == "/api/unlink":
            install_id = data.get("install_id")
            repo_id = data.get("repo_id")
            if self.config.unlink_repository_from_installation(install_id, repo_id):
                self.config.save_config()
                self._send_json_response({"success": True})
            else:
                self._send_json_response({"success": False, "error": "Not linked"}, 400)
        elif parsed_url.path == "/api/perform_link":
            # Actually create the symbolic links
            install_id = data.get("install_id")
            repo_id = data.get("repo_id")
            
            install = next((i for i in self.config.data["comfyui_installations"] if i["id"] == install_id), None)
            repo = next((r for r in self.config.data["repositories"] if r["id"] == repo_id), None)
            
            if not install or not repo:
                self._send_json_response({"success": False, "error": "Installation or repository not found"}, 404)
                return
            
            # Perform the actual linking
            results = self.linker.link_repository_to_installation(repo["path"], install["path"], repo_id, self.config)

            # Also update the configuration
            self.config.link_repository_to_installation(install_id, repo_id)
            
            # Update link status
            self.config.update_all_link_status(self.linker)
            self.config.save_config()
            
            self._send_json_response({"success": True, "results": results})
        elif parsed_url.path == "/api/perform_unlink":
            # Actually remove the symbolic links
            install_id = data.get("install_id")
            repo_id = data.get("repo_id")
            
            install = next((i for i in self.config.data["comfyui_installations"] if i["id"] == install_id), None)
            repo = next((r for r in self.config.data["repositories"] if r["id"] == repo_id), None)
            
            if not install or not repo:
                self._send_json_response({"success": False, "error": "Installation or repository not found"}, 404)
                return
            
            # Perform the actual unlinking (remove symlinks for this specific repository)
            results = self.linker.unlink_repository_from_installation(repo["path"], install["path"], repo_id, self.config)

            # Also update the configuration
            self.config.unlink_repository_from_installation(install_id, repo_id)
            
            # Update link status
            self.config.update_all_link_status(self.linker)
            self.config.save_config()
            
            self._send_json_response({"success": True, "results": results})
        elif parsed_url.path == "/api/toggle_custom_folder":
            # Toggle a custom folder for a repository
            repo_id = data.get("repo_id")
            folder_name = data.get("folder_name")

            if not repo_id or not folder_name:
                self._send_json_response({"success": False, "error": "Missing repo_id or folder_name"}, 400)
                return

            # Get OLD state before toggling (needed for unlinking)
            old_enabled_folders = self.config.get_enabled_custom_folders(repo_id).copy()

            # Toggle the folder (changes the state)
            enabled = self.config.toggle_custom_folder(repo_id, folder_name)

            # Get NEW state after toggling (needed for linking)
            new_enabled_folders = self.config.get_enabled_custom_folders(repo_id)

            # Find the repository
            repo = next((r for r in self.config.data["repositories"] if r["id"] == repo_id), None)
            if not repo:
                self._send_json_response({"success": False, "error": "Repository not found"}, 404)
                return

            # Refresh links for all installations that have this repo linked
            # This ensures symlinks are in sync with the enabled state
            for install_key, linked_repos in self.config.data["links"].items():
                if repo_id in linked_repos:
                    install_id = int(install_key)
                    install = next((i for i in self.config.data["comfyui_installations"] if i["id"] == install_id), None)
                    if install and install["exists"]:
                        print(f"DEBUG: Toggling {folder_name} (enabled={enabled}) for installation {install_id}")
                        print(f"DEBUG: Old enabled folders: {old_enabled_folders}")
                        print(f"DEBUG: New enabled folders: {new_enabled_folders}")

                        # Unlink using OLD state (so disabled folders get removed)
                        self._unlink_with_custom_folders(repo["path"], install["path"], old_enabled_folders)
                        # Link using NEW state (so newly enabled folders get added)
                        self._link_with_custom_folders(repo["path"], install["path"], new_enabled_folders)

            # Update link status
            self.config.update_all_link_status(self.linker)
            self.config.save_config()

            self._send_json_response({"success": True, "enabled": enabled, "folder_name": folder_name})
        elif parsed_url.path == "/api/refresh_paths":
            self.config.refresh_all_paths()
            self.config.save_config()
            self._send_json_response({"success": True})
        elif parsed_url.path == "/api/update_link_status":
            # Update link status for all installations
            self.config.update_all_link_status(self.linker)
            self.config.save_config()
            self._send_json_response({"success": True, "message": "Link status updated for all installations"})
        elif parsed_url.path == "/api/check_repository_changes":
            # Check all repositories for changes
            changes = self.config.check_all_repositories_for_changes()
            self.config.save_config()  # Save updated snapshots
            self._send_json_response(changes)
        elif parsed_url.path == "/api/repository_changes":
            repo_id = data.get("repo_id")
            if repo_id:
                changes = self.config.detect_repository_changes(repo_id)
                self.config.save_config()  # Save updated snapshot
                self._send_json_response({"success": True, "changes": changes})
            else:
                self._send_json_response({"success": False, "error": "Missing repo_id parameter"}, 400)
        else:
            self.send_error(404, "Not found")
    
    def do_PUT(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        parsed_url = urlparse(self.path)
        
        if parsed_url.path.startswith("/api/repositories/"):
            repo_id = int(parsed_url.path.split("/")[-1])
            repo = self.config.update_repository(
                repo_id,
                data.get("name"),
                data.get("path"),
                data.get("description")
            )
            if repo:
                self.config.save_config()
                self._send_json_response(repo)
            else:
                self.send_error(404, "Repository not found")
        elif parsed_url.path.startswith("/api/installations/"):
            install_id = int(parsed_url.path.split("/")[-1])
            installation = self.config.update_comfyui_installation(
                install_id,
                data.get("name"),
                data.get("path"),
                data.get("description")
            )
            if installation:
                self.config.save_config()
                self._send_json_response(installation)
            else:
                self.send_error(404, "Installation not found")
        else:
            self.send_error(404, "Not found")
    
    def do_DELETE(self):
        parsed_url = urlparse(self.path)
        
        if parsed_url.path.startswith("/api/repositories/"):
            repo_id = int(parsed_url.path.split("/")[-1])
            self.config.delete_repository(repo_id)
            self.config.save_config()
            self._send_json_response({"success": True})
        elif parsed_url.path.startswith("/api/installations/"):
            install_id = int(parsed_url.path.split("/")[-1])
            self.config.delete_comfyui_installation(install_id)
            self.config.save_config()
            self._send_json_response({"success": True})
        else:
            self.send_error(404, "Not found")
    
    def _unlink_with_custom_folders(self, repo_path, install_path, custom_folder_names):
        """Unlink standard folders + specific custom folders"""
        results = {}
        models_path = os.path.join(install_path, "models")

        # Unlink standard folders
        for folder in self.linker.standard_folders:
            src_folder = os.path.join(repo_path, folder)
            dest_folder = os.path.join(models_path, folder)
            if os.path.exists(dest_folder):
                results[folder] = self.linker._unlink_folder_for_repository(src_folder, dest_folder, folder)

        # Unlink specified custom folders
        for folder in custom_folder_names:
            src_folder = os.path.join(repo_path, folder)
            dest_folder = os.path.join(models_path, folder)
            if os.path.exists(dest_folder):
                print(f"DEBUG: Unlinking custom folder {folder}")
                results[folder] = self.linker._unlink_folder_for_repository(src_folder, dest_folder, folder)

        return results

    def _link_with_custom_folders(self, repo_path, install_path, custom_folder_names):
        """Link standard folders + specific custom folders"""
        results = {}
        models_path = os.path.join(install_path, "models")

        if not os.path.exists(models_path):
            os.makedirs(models_path, exist_ok=True)

        # Link standard folders
        for folder in self.linker.standard_folders:
            src_folder = os.path.join(repo_path, folder)
            dest_folder = os.path.join(models_path, folder)
            if os.path.exists(src_folder):
                results[folder] = self.linker._link_folder(src_folder, dest_folder, folder)

        # Link specified custom folders
        for folder in custom_folder_names:
            src_folder = os.path.join(repo_path, folder)
            dest_folder = os.path.join(models_path, folder)
            if os.path.exists(src_folder):
                print(f"DEBUG: Linking custom folder {folder}")
                results[folder] = self.linker._link_folder(src_folder, dest_folder, folder)

        return results

    def serve_main_interface(self):
        # Serve the actual HTML file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        html_file = os.path.join(script_dir, 'model_manager.html')
        
        try:
            with open(html_file, 'r') as f:
                html_content = f.read()
            self._send_html_response(html_content)
        except FileNotFoundError:
            # Fallback to basic interface if HTML file not found
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>ComfyUI Model Manager</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; background: #1e1e1e; color: #d4d4d4; }
                    h1 { color: #569cd6; }
                </style>
            </head>
            <body>
                <h1>🎨 ComfyUI Model Manager</h1>
                <p>HTML file not found. Please ensure model_manager.html is in the same directory as model_manager.py</p>
                <p>Expected location: """ + html_file + """</p>
            </body>
            </html>
            """
            self._send_html_response(html)

def classify_safetensor(filename, metadata=None, tensor_keys=None):
    """Classify SafeTensor models based on filename, metadata, and tensor keys"""
    lower = filename.lower()
    
    # Check metadata first for more accurate classification
    if metadata and isinstance(metadata, dict):
        architecture = metadata.get("modelspec.architecture", "")
        if "flux-1-dev/lora" in architecture.lower():
            return "LORA for Flux"
        elif "lora" in architecture.lower():
            return "LORA"
    
    # Enhanced tensor keys analysis for more accurate classification
    if tensor_keys and isinstance(tensor_keys, list):
        tensor_keys_str = " ".join(tensor_keys).lower()
        
        # Check for specific tensor key patterns first
        if any(k.startswith("controlnet_") for k in tensor_keys):
            return "ControlNet"
        elif any("text_encoder" in k or "clip" in k for k in tensor_keys):
            return "Checkpoint"
        elif tensor_keys and all(k.startswith("lora_") or "adapter" in k for k in tensor_keys):
            return "LoRA"
        elif tensor_keys and all("." not in k and k.endswith(".embeddings") for k in tensor_keys):
            return "Embedding"
        
        # Check for other patterns
        elif "lora" in tensor_keys_str:
            return "LORA"
        elif "temporal_transformer" in tensor_keys_str:
            return "Temporal Animation Model"
    
    # Fallback to filename-based classification
    if "control" in lower:
        return "ControlNet"
    elif "lora" in lower or "adapter" in lower:
        return "LORA"
    elif "vae" in lower:
        return "VAE"
    elif "unet" in lower and not "control" in lower:
        return "UNet"
    else:
        return "Checkpoint/Model"

if __name__ == "__main__":
    port = 8002
    print(f"ComfyUI Model Manager starting on http://localhost:{port}")
    
    # Initialize and update link status on startup
    config = ModelManagerConfig()
    linker = ModelLinker()
    
    print("Checking link status for all installations...")
    config.update_all_link_status(linker)
    config.save_config()
    print("✓ Link status updated")
    
    httpd = HTTPServer(("0.0.0.0", port), ModelManagerHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Model Manager...")
    finally:
        httpd.server_close()
        print("Model Manager stopped.") 