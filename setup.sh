
#!/usr/bin/env bash
set -e

echo "=================================="
echo " Setting up Python dependencies"
echo "=================================="

# Installing ROPE outside the parent folder
cd ..
git clone https://github.com/nikolaj-zwergius/ROPE.git
cd ROPE
python3 install.py --mode edit
cd ../BlueprintDesigner




# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "[1/5] Creating virtual environment..."
    python3 -m venv .venv
else
    echo "[1/5] Virtual environment already exists."
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
echo "[2/5] Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
echo "[3/5] Installing packages..."
python -m pip install PySide6 pyfurnace

# Verify installation
echo "[4/5] Verifying dependencies..."
python -c "import PySide6; import pyfurnace; print('All dependencies installed successfully!')"

echo "[5/5] Installing BlueprintDesigner..."
python -m pip install -e .

echo ""
echo "=================================="
echo " Setup complete!"
echo "=================================="
echo "Activate your environment with:"
echo "source .venv/bin/activate"
echo "To run BlueprintDesigner simply type 'blueprint-designer' in terminal to initiate the program"


