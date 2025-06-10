# Git Repository Setup Guide

This guide helps you prepare and upload the ComfyUI Model Manager to GitHub.

## 📋 Pre-Upload Checklist

### ✅ Files Ready for Git
- [x] `.gitignore` - Excludes test folders, venv, config files
- [x] `README.md` - Comprehensive project documentation
- [x] `model_manager_config.example.json` - Example configuration
- [x] Core application files
- [x] Assets and screenshots

### ❌ Files Excluded (via .gitignore)
- Test folders (`testfolders/`)
- Virtual environment (`venv/`)
- User configuration (`model_manager_config.json`)
- Model files (*.safetensors, *.ckpt, etc.)
- Cache and temporary files

## 🚀 Git Commands to Upload

### 1. Initialize Repository (if not done)
```bash
git init
```

### 2. Add Remote Repository
Replace `USERNAME` and `REPO_NAME` with your GitHub details:
```bash
git remote add origin https://github.com/USERNAME/REPO_NAME.git
```

### 3. Stage All Files
```bash
git add .
```

### 4. Check What Will Be Committed
```bash
git status
```

### 5. Commit Changes
```bash
git commit -m "Initial commit: ComfyUI Model Manager with integrated SafeTensor Inspector

- Complete model management system for multiple ComfyUI installations
- Integrated SafeTensor Inspector for metadata analysis
- Symbolic link management for shared model repositories
- Modern web UI with tabbed interface
- Path validation and change detection
- Screenshots and comprehensive documentation"
```

### 6. Push to GitHub
```bash
git branch -M main
git push -u origin main
```

## 🔧 Repository Suggestions

### Repository Name Ideas
- `comfyui-model-manager`
- `comfyui-manager-inspector`
- `model-manager-safetensor`
- `comfyui-toolkit`

### Repository Description
```
A comprehensive web tool for managing multiple ComfyUI installations and model repositories with integrated SafeTensor inspection. Eliminate model duplication through smart symbolic linking.
```

### Topics/Tags
```
comfyui
model-management
safetensor
symbolic-links
python
flask
ai-models
stable-diffusion
web-interface
```

## 📁 What Gets Uploaded

### Core Files (✅ Included)
```
├── README.md                           # Main documentation
├── model_manager.py                    # Backend server
├── model_manager.html                  # Frontend interface
├── requirements.txt                    # Python dependencies
├── setup.sh                           # Environment setup
├── start_model_manager.sh             # Application launcher
├── model_manager_config.example.json  # Example configuration
├── assets/
│   ├── screenshots/                   # UI screenshots
│   └── banner*.png                    # Header banners
├── .gitignore                         # Git exclusions
└── GIT_SETUP.md                       # This file
```

### User Files (❌ Excluded)
```
├── testfolders/                       # Your test directories
├── venv/                              # Python virtual environment
├── model_manager_config.json          # Your personal configuration
├── *.safetensors                      # Model files
└── __pycache__/                       # Python cache
```

## 🛡️ Security Notes

- Personal paths are excluded from upload
- No actual model files included
- Configuration contains only example paths
- Virtual environment excluded to prevent bloat

## 🎯 After Upload

### Users Will Need To:
1. Clone the repository
2. Run `./setup.sh` to create virtual environment
3. Copy and customize `model_manager_config.example.json`
4. Add their own repositories and installations
5. Run `./start_model_manager.sh`

### Consider Adding:
- GitHub Issues templates
- Contributing guidelines
- License file (MIT, GPL, etc.)
- GitHub Actions for testing
- Release tags for versions

## 🔄 Future Updates

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "Add feature: [description]"

# Push updates
git push origin main
```

Your repository is now ready for Git! 🎉 