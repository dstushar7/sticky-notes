#!/bin/bash

# This script automates the cleaning, rebuilding, and reinstallation
# of the 'stickynotes' snap package.

# Exit immediately if a command exits with a non-zero status.
set -e

SNAP_NAME="stickynotes"

echo "--- Removing old version of $SNAP_NAME ---"
# Attempt to remove the snap. If it's not installed, this will fail.
# '|| true' ensures the script doesn't exit if the snap isn't found.
sudo snap remove $SNAP_NAME || true

echo "--- Cleaning the project with destructive-mode ---"
# Clean the project directory. We use 'sudo' to handle any files
# created by a root process in previous builds.
snapcraft clean --destructive-mode

echo "--- Packing the new snap ---"
# Create the new .snap package.
snapcraft pack --destructive-mode

echo "--- Installing the new snap package ---"
# Find the most recently created .snap file to install it.
# This avoids hardcoding the version number.
SNAP_FILE=$(find . -name "*.snap" -printf "%T@ %p\n" | sort -n | tail -1 | cut -d' ' -f2-)
sudo snap install "$SNAP_FILE" --dangerous

echo "--- Rebuild and reinstall complete! ---"
