#!/bin/bash

# ANSI Colors
CYAN="\033[1;36m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
RESET="\033[0m"

# Banner with ASCII art and timestamp
echo -e "${CYAN}--- Running setup script for ComfyUI Model Manager @ ${GREEN}$(date)${CYAN}"
cat <<'EOF'
  ___|                  _|       |   |_ _|  \  |           |      |  \  |
 |      _ \  __ `__ \  |   |   | |   |  |  |\/ |  _ \   _` |  _ \ | |\/ |  _` | __ \   _` |  _` |  __|
 |     (   | |   |   | __| |   | |   |  |  |   | (   | (   |  __/ | |   | (   | |   | (   | (   | |
\____|\___/ _|  _|  _|_|  \__, |\___/ ___|_|  _|\___/ \__,_|\___|_|_|  _|\__,_|_|  _|\__,_|\__, |_|
    ComfyUI Model Manager ____/                                                            |___/
EOF

PYTHON_CMD="python3"
VENV_DIR="venv"

# Check for Python 3
if ! command -v $PYTHON_CMD &> /dev/null
then
    echo -e "${RED}Error: Python 3 is not installed or not in PATH. Please install Python 3.${RESET}"
    exit 1
fi

echo -e "${CYAN}--- ComfyUI Model Manager Setup ---${RESET}"

# Check if virtual environment already exists
if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Virtual environment '$VENV_DIR' already exists.${RESET}"
else
    echo -e "${GREEN}Creating Python virtual environment in '$VENV_DIR'...${RESET}"
    $PYTHON_CMD -m venv $VENV_DIR
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to create virtual environment.${RESET}"
        exit 1
    fi
fi

# Activate virtual environment and install requirements
echo -e "${GREEN}Activating virtual environment and installing dependencies...${RESET}"

# Use the venv's pip directly to ensure we're installing in the right place
VENV_PIP="$VENV_DIR/bin/pip"
VENV_PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$VENV_PIP" ] || [ ! -f "$VENV_PYTHON" ]; then
    echo -e "${RED}Error: Virtual environment seems incomplete. Try deleting '$VENV_DIR' and running setup again.${RESET}"
    exit 1
fi

echo -e "${BLUE}Installing packages from requirements.txt using $VENV_PIP...${RESET}"
"$VENV_PIP" install -r requirements.txt

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to install dependencies. Please check requirements.txt and ensure pip is working.${RESET}"
    echo -e "${YELLOW}You might need to activate the virtual environment manually ('source $VENV_DIR/bin/activate') and then run 'pip install -r requirements.txt'.${RESET}"
    exit 1
fi

echo -e "${GREEN}✓ Dependencies installed successfully.${RESET}"

# Verify installation by checking if safetensors is importable
echo -e "${BLUE}Verifying safetensors installation...${RESET}"
"$VENV_PYTHON" -c "import safetensors; print('✓ safetensors import successful')" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ safetensors library is properly installed and importable.${RESET}"
else
    echo -e "${YELLOW}⚠ Warning: safetensors library may not be properly installed. The application will run with limited functionality.${RESET}"
fi

# Make start script executable if it's not already
echo -e "${BLUE}Making start script executable...${RESET}"
if [ ! -x "start_model_manager.sh" ]; then
    chmod +x "start_model_manager.sh"
fi
echo -e "${GREEN}✓ Start script is executable.${RESET}"
echo -e "To run the application: ${YELLOW}./start_model_manager.sh${RESET}"
echo -e "${CYAN}--- Setup Complete @ ${GREEN}$(date)${RESET}"

    
