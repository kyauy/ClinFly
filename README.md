---
title: Linguo Franca
emoji: incoming_envelope
sdk: streamlit
sdk_version: 1.19.0 
app_file: clinfly_app.py
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

## Run the framework

A webapp is accessible at [https://huggingface.co/spaces/kyauy/ClinFly](https://huggingface.co/spaces/kyauy/ClinFly), **please try it !**

It's a streamlit application, where code is accessible in ̀`clinfly_app.py` file. 

To install on your local machine, you need `poetry` package manager and launch in the folder:
```
poetry install
```

To make it run in your local computer:
```
poetry shell
streamlit run clinfly_app.py
```

Using requirement ?
```
poetry export --without-hashes --format=requirements.txt > requirements.txt
```