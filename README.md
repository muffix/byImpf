# ImpfChecker

Basic checker for Bavaria's booking portal for vaccination appointments. 
Checks the portal for the first available appointment and prints it. 

## Requirements

- You need to be registered with the portal at https://impfzentren.bayern/citizen/
- You need to have selected a vaccination centre in the portal
- Python 3

## How to run

### Install the dependencies

Just run 
```shell
pip install -r requirements.txt
```

### Run the checker

The checker requires your username, password, and citizen ID in the environment variables `USER`, `PASSWORD`, 
and `CITIZEN_ID`, respectively.

You can find your citizen ID if you login to the portal and select the person. The address bar in your browser contains 
the ID in the following format: `https://impfzentren.bayern/citizen/overview/{CITIZEN_ID}`.
 
```shell
python impf.py
```
