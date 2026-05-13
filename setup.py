from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# get version from __version__ variable in alphax_wallet/__init__.py
from alphax_wallet import __version__ as version

setup(
    name="alphax_wallet",
    version=version,
    description="AlphaX Wallet - Customer wallet, booking integration, and multi-party settlement for ERPNext",
    author="AlphaX",
    author_email="support@alphax.local",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
