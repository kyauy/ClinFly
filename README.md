---
title: ClinFly
emoji: small_airplane
sdk_version: 1.25.0 
sdk: streamlit
app_file: clinfly_app_st.py
pinned: true
---

# ClinFly

![](img/clinfly_logo.png)


Contact : [kevin.yauy@chu-montpellier.fr](mailto:kevin.yauy@chu-montpellier.fr)

## Introduction

ClinFly is an automated framework designed to facilitate precision medicine (PM) for rare diseases. It addresses the challenge of precision phenotyping and data sharing across different languages.

ClinFly can anonymize, translate, and summarize clinical reports using Human Phenotype Ontology (HPO) terms, ensuring compliance with medical data privacy standards. The output includes a de-identified translated clinical report and a summary report in HPO format.

By streamlining the translation and anonymization of clinical reports, ClinFly aims to enhance inter-hospital data sharing, expedite medical discoveries, and pave the way for an international patient file accessible to non-English speakers.

## Pipeline 

![](img/pipeline.png)

## Installation

To install ClinFly on your local machine, you need the `poetry` package manager. Navigate to the project folder and run:

```
poetry install
```

If you need to generate a `requirements.txt` file, use the following command:
```
poetry export --without-hashes --format=requirements.txt > requirements.txt
```

## Usage

### Graphical User Interface 

For single report usage with interactive analysis, ClinFly provides a web application accessible at https://huggingface.co/spaces/kyauy/ClinFly.

To run the Streamlit application on your local computer, activate the poetry shell and run the `clinfly_app_st.py` file:
```
poetry shell
streamlit run clinfly_app_st.py
```

### Command Line Interface

For processing multiple reports with offline options, use the command line interface provided by `clinfly_app_cli.py`.

The input should be a TSV .txt file structured as follows (see `data/test.tsv` for an example):
```
Report_id_1   Doe  John  Report text 
...
Report_id_X   Doe  John  Report text
```

Outputs will be placed in the `results` folder according to the file extension, using first three columns in filename. 
- The deidentify report will be generated and placed in the `results/Reports` folder.
- Three HPO extraction outputs will be generated in `TSV`, `TXT` and `JSON` folders.

To run the CLI application on your local computer :
```
poetry shell
<python running version> clinfly_app_cli.py --file <input txt file with the reports> --language <language of the file> --model_dir <The output directory of the model (OPTIONAL)> --result_dir <The output directory of the generated result (OPTIONAL)>
```
