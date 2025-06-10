#!/bin/bash

# ANSI colors
CYAN="\033[1;36m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

VENV_DIR="venv"

# Check if we're in the virtual environment
if [ -z "$VIRTUAL_ENV" ] || [ "$(basename "$VIRTUAL_ENV")" != "$VENV_DIR" ]; then
    echo -e "${YELLOW}Virtual environment not active. Attempting to activate '$VENV_DIR'...${RESET}"
    
    # Try to activate the virtual environment
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
        echo -e "${GREEN}✓ Activated virtual environment in $VENV_DIR${RESET}"
    else
        echo -e "${RED}Error: Virtual environment '$VENV_DIR' not found.${RESET}"
        echo -e "Please create it first by running: ${GREEN}./setup.sh${RESET}"
        exit 1
    fi
fi

# Verify we can find the Python interpreter in the venv
PYTHON_EXEC="$VENV_DIR/bin/python"
if [ ! -f "$PYTHON_EXEC" ]; then
    echo -e "${RED}Error: Python executable not found in virtual environment at $PYTHON_EXEC${RESET}"
    exit 1
fi

# Function to handle cleanup
cleanup() {
    echo -e "\n${CYAN}Shutting down Model Manager...${RESET}"
    if [ -n "$SERVER_PID" ]; then
        kill -TERM "$SERVER_PID" 2>/dev/null
        wait "$SERVER_PID" 2>/dev/null
    fi
    echo -e "${CYAN}Model Manager stopped.${RESET}"
    exit 0
}

# Set up trap to catch termination signals
trap cleanup SIGINT SIGTERM

# Banner
echo -e "$CYAN"
cat <<'EOF'
  ___|                  _|       |   |_ _|  \  |           |      |  \  |                              
 |      _ \  __ `__ \  |   |   | |   |  |  |\/ |  _ \   _` |  _ \ | |\/ |  _` | __ \   _` |  _` |  __| 
 |     (   | |   |   | __| |   | |   |  |  |   | (   | (   |  __/ | |   | (   | |   | (   | (   | |    
\____|\___/ _|  _|  _|_|  \__, |\___/ ___|_|  _|\___/ \__,_|\___|_|_|  _|\__,_|_|  _|\__,_|\__, |_|    
    ComfyUI Model Manager ____/                                                            |___/       
    Manage repositories and model linking. Thanks to the wuzzes for the ascii art.
EOF
echo -e "$RESET"

# Start the Model Manager
echo -e "${GREEN}Starting ComfyUI Model Manager...${RESET}"
echo -e "${CYAN}Using Python: $PYTHON_EXEC${RESET}"

"$PYTHON_EXEC" model_manager.py &
SERVER_PID=$!

# Give the server a moment to initialize
sleep 1

# Check if server started successfully
if ! ps -p $SERVER_PID > /dev/null; then
    echo -e "${RED}Error: Failed to start the Model Manager.${RESET}" >&2
    exit 1
fi

echo -e "${GREEN}ComfyUI Model Manager is running on http://localhost:8002 (PID: $SERVER_PID)${RESET}"
echo -e "${YELLOW}Press Ctrl+C to stop the server.${RESET}"

# Optional: Ask to open browser
read -p "Open Model Manager in browser now? (y/n): " open_browser
if [[ "$open_browser" == "y" || "$open_browser" == "Y" ]]; then
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8002
    elif command -v open &> /dev/null; then # macOS
        open http://localhost:8002
    elif command -v start &> /dev/null; then # Windows (Git Bash, etc.)
        start http://localhost:8002
    else
        echo -e "${YELLOW}Could not detect a command to open the browser. Please open http://localhost:8002 manually.${RESET}"
    fi
fi

# Wait for the server process
wait $SERVER_PID 