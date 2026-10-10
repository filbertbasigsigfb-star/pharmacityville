# Example PythonAnywhere WSGI file. Update YOUR_USERNAME and your venv in Web tab.
import sys
project_path = '/home/YOUR_USERNAME/pharmacityville'
if project_path not in sys.path:
    sys.path.insert(0, project_path)
from app import app as application
