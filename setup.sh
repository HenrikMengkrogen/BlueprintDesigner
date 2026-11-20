
#!/usr/bin/env bash
set -e

echo "=================================="
echo " Setting up Python dependencies"
echo "=================================="

cd ..
git clone https://github.com/nikolaj-zwergius/ROPE.git
cd ROPE
python install.py
cd ..
cd Blueprint_Designer

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "[1/4] Creating virtual environment..."
    python3 -m venv .venv
else
    echo "[1/4] Virtual environment already exists."
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
echo "[2/4] Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
echo "[3/4] Installing packages..."
python -m pip install PySide6 pyfurnace

# Verify installation
echo "[4/4] Verifying dependencies..."
python -c "import PySide6; import pyfurnace; print('All dependencies installed successfully!')"

echo ""
echo "=================================="
echo " Setup complete!"
echo "=================================="
echo "Activate your environment with:"
echo "source .venv/bin/activate"

