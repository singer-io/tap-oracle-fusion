from setuptools import find_packages, setup

setup(
    name="tap-oracle-fusion",
    version="0.0.1",
    description="Singer.io tap for extracting data from oracle-fusion API",
    author="Stitch",
    url="http://singer.io",
    classifiers=["Programming Language :: Python :: 3 :: Only"],
    py_modules=["tap_oracle_fusion"],
    install_requires=[
        "singer-python==6.1.1",
        "requests==2.32.5",
        "backoff==2.2.1"
    ],
    entry_points="""
          [console_scripts]
          tap-oracle-fusion=tap_oracle_fusion:main
      """,
    packages=find_packages(),
    package_data={
        "tap_oracle_fusion": ["schemas/*.json"],
    },
    include_package_data=True,
)
