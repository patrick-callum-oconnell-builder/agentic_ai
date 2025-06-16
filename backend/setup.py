from setuptools import setup, find_packages

setup(
    name="agent_personal_trainer",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "google-api-python-client",
        "google-auth-httplib2",
        "google-auth-oauthlib",
        "python-dotenv",
    ],
) 