"""Shared pytest fixtures and configuration."""
import sys
import os

# Ensure the project root is on sys.path so lumina_control is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
