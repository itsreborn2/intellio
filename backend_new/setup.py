from setuptools import setup, find_packages

setup(
    name="intellio",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "google-generativeai",
        "python-multipart",
        "python-jose[cryptography]",
        "passlib[bcrypt]",
        "tenacity",
        "loguru",
        "pytest",
        "pytest-asyncio",
    ],
    python_requires=">=3.11",
)
