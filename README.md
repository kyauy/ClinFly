---
title: ClinFly
emoji: small_airplane
sdk_version: 1.21.0 
streamlit_file: clinfly_app_st.py
CLI_file: clinfly_app_cli.py
pinned: true
---

# ClinFly

![](img/clinfly_logo.png)


Contact : [kevin.yauy@chu-montpellier.fr](mailto:kevin.yauy@chu-montpellier.fr)

## Introduction

Precision medicine (PM) for rare diseases requires both precision phenotyping and data sharing. However, the majority of digital phenotyping tools only deal with the English language. 

Using French as a proof of concept, we have developed ClinFly, an automated framework to anonymize, translate and summarize clinical reports using Human Phenotype Ontology (HPO) terms compliant with medical data privacy standards. The output consists of a de-identified translated clinical report and a summary report in HPO format. 

By facilitating the translation and anonymization of clinical reports, ClinFly has the potential to facilitate inter-hospital data sharing, accelerate medical discoveries and open up the possibility of an international patient file without limitations due to non-English speakers.

## Pipeline 

![](img/pipeline.png)

## Poetry Installation

To install on your local machine, you need `poetry` package manager and launch in the folder:
```
poetry install
```

Using requirement ?
```
poetry export --without-hashes --format=requirements.txt > requirements.txt
```

## Run the code

### Graphical User Interface - Single report usage with interactive analysis

A webapp is accessible at https://huggingface.co/spaces/kyauy/ClinFly, please try it !

It's a streamlit application, where code is accessible in ̀`clinfly_app_st.py` file. The functions are accessible in the `utilities` folder.

To run the streamlit application on your local computer :
```
poetry shell
streamlit run clinfly_app_st.py
```

### Command Line Interface - Multiple report usage with offline options

The code is accessible in ̀`clinfly_app_cli.py` file. The functions are accessible in the `utilities` folder.

The entry file must be a TSV .txt with the informations structured like this :
```
Doe  John  Report
```

The output will be placed in the `results` folder according to the file extension. 

A resume of the deidentify report will be generated and placed in the `results/Reports` folder.

Three HPO extraction output will be generated, TSV, TXT and Json.

To run the CLI application on your local computer :
```
poetry shell
<python running version> clinfly_app_cli.py --file <input csv file with the reports> --language <language of the file> --output_dir <The output directory of the model (OPTIONAL)>
```
