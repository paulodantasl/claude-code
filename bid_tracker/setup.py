from setuptools import find_packages, setup

setup(
    name="bid-tracker",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "anthropic>=0.40.0",
        "requests>=2.31.0",
        "feedparser>=6.0.11",
        "beautifulsoup4>=4.12.0",
        "playwright>=1.40.0",
        "pydantic>=2.5.0",
        "sqlalchemy>=2.0.0",
        "pyyaml>=6.0.1",
        "python-dotenv>=1.0.0",
        "rich>=13.7.0",
        "click>=8.1.7",
        "tenacity>=8.2.0",
        "jinja2>=3.1.0",
    ],
    entry_points={
        "console_scripts": [
            "bid-tracker=bid_tracker.main:main",
        ],
    },
)
