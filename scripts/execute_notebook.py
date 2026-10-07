"""Execute all cells using this Python environment; no preinstalled kernel needed."""

import os
import sys
from pathlib import Path

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient

root = Path(__file__).resolve().parents[1]
path = root / "notebooks" / "demo.ipynb"
# Select the running environment rather than a user's unrelated global Python kernel.
manager = KernelManager(kernel_name="python3")
manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
notebook = nbformat.read(path, as_version=4)
client = NotebookClient(
    notebook, km=manager, timeout=180, resources={"metadata": {"path": str(root)}}
)
try:
    client.execute()
finally:
    if manager.has_kernel:
        manager.shutdown_kernel(now=True)
nbformat.write(notebook, path)
print(
    f"Executed {sum(c.cell_type == 'code' for c in notebook.cells)} cells; mode={os.getenv('RAG_MODE', 'mock')}."
)
