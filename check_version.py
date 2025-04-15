import importlib.metadata

try:
    version = importlib.metadata.version("aiogram")
    print(f"Aiogram version: {version}")
except importlib.metadata.PackageNotFoundError:
    print("Aiogram is not installed")