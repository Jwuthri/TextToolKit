from setuptools import setup, find_packages

version = "0.1.1"

setup(
    name="maupassant",
    version=version,
    license="proprietary",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "tensorflow-gpu==2.3.1",
        "tensorflow-hub==0.7.0",
        "tensorflow-text==2.1.1",
        "autocorrect==2.0.0",
        "comet-ml==3.2.0",
        "emot==2.1",
        "nltk==3.5",
        "pandas==1.0.0",
        "pydot==1.4.1",
        "pytest==5.2.0",
        "scikit-learn==0.23.0",
        "streamlit==0.65.0",
        "umap-learn==0.3.10",
        "contractions==0.0.25",
        "python-dotenv==0.14.0"
    ]
)
