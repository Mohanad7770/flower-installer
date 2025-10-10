from setuptools import setup, find_packages

setup(
    name="flower-installer",
    version="1.0.0",
    author="Beach Cities Software, LLC",
    author_email="apps@beachcitiessoft.com",
    description="CLI for installing Celery Flower with Apache/Nginx, SSL, auth, and systemd",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "jinja2>=3.0",
    ],
    entry_points={"console_scripts": ["flowerctl=flower_installer.cli:main"]},
    python_requires=">=3.8",
    license="MIT",
)
