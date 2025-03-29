#!/bin/bash
# Install script for Book & Paper Renamer

set -e  # Exit on error

echo "Installing Book & Paper Renamer..."

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Install the package
echo "Installing Book & Paper Renamer..."
pip install -e .

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from example.env..."
    cp example.env .env
    echo "Please edit .env to add your Perplexity API key"
fi

echo "Installation complete!"
echo "To use the tool:"
echo "1. Edit the .env file and add your Perplexity API key"
echo "2. Activate the virtual environment: source venv/bin/activate"
echo "3. Run the tool: book-renamer /path/to/your/books"
echo ""
echo "For more options, run: book-renamer --help" 