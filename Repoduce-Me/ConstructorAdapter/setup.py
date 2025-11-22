from setuptools import setup, find_packages

setup(
    name="constructor_adapter",  # Name of your package
    version="0.3.1",             # Version number
    description="A Python package for interacting with Constructor APIs",
    author="Your Name",
    author_email="giancarlo.succi@gmail.com",
    url="https://github.com/GiancarloSucci/ConstructorAdapter",  # URL of the repository
    packages=find_packages(),    # Automatically discover sub-packages
    install_requires=[
        "requests",              # List dependencies here
        "dotenv",
        "python-dotenv"
    ],
    python_requires=">=3.7",     # Specify Python version compatibility
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)