from setuptools import find_packages, setup

setup(
    name="job_reviewer",
    version="0.1.0",
    description="Review government job postings against your resume and flag the best fits.",
    packages=find_packages(),
    include_package_data=True,
    package_data={"job_reviewer": ["targets/*.yaml", "profile/*"]},
    install_requires=[
        "anthropic>=0.40.0",
        "playwright>=1.40.0",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=5.0.0",
        "sqlalchemy>=2.0.0",
        "pyyaml>=6.0.1",
        "python-dotenv>=1.0.0",
        "rich>=13.7.0",
        "click>=8.1.7",
        "pypdf>=4.0.0",
        "python-docx>=1.1.0",
    ],
    entry_points={"console_scripts": ["job-reviewer=job_reviewer.main:main"]},
    python_requires=">=3.10",
)
