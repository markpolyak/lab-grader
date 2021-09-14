from setuptools import setup, find_packages

setup(
    name='lab_grader',
    version='1.0.0',
    packages=find_packages(),
    install_requires=[
        'requests~=2.26.0',
        'oauth2client~=4.1.3',
        'google-api-python-client~=2.20.0',
        'bottle~=0.12.19',
        'google-auth-oauthlib~=0.4.6',
        'python-dateutil~=2.8.2',
        'pyyaml~=5.4.1',
        'beautifulsoup4~=4.10.0',
        'mosspy~=1.0.9'
    ]
)
