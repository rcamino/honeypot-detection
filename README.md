# honeypot-detection
Code for the paper ["A Data Science Approach for Honeypot Detection in Ethereum"](https://arxiv.org/abs/1910.01449).

## Pre-requisites

The crawler and feature extractor was developed using python 3.6.8 with the following packages:

- numpy==1.17.4
- requests==2.22.0
- SQLAlchemy==1.3.11

For the machine learning experiments add the following packages:

- jupyter==1.0.0
- matplotlib==3.1.2
- pandas==0.25.3
- scikit-learn==0.21.3
- xgboost==0.90

To install al the packages with pip:

```bash
pip install -r requirements.txt
```

You can optionally install any SQLAlchemy compatible database to store the data.

Sqlite is used by default (no additional installation required).

Other databases were not tested yet.

All instructions below are expected to be executed inside the project root.

Most of the scripts can show a help message when the argument ``-h`` present.

## Configuration

First copy the configuration file example:

```bash
cp honeypot_detection/config.example.py honeypot_detection/config.py
```

Then edit the configuration file:

- Replace the Etherscan API key inside the ``create_etherscan_client`` method [(help here)](https://etherscan.io/apis);
- You can change the SQLAlchemy connection URI inside the ``create_sqlalchemy_engine`` method
[(help here)](https://docs.sqlalchemy.org/en/13/core/engines.html);
- You can change the logging configuration using ``logging.basicConfig``
[(help here)](https://docs.python.org/3/library/logging.html#logging.basicConfig).

Then generate the tables by executing:

```bash
python honeypot_detection/database/create_tables.py
```

For the following examples, we need to create the data directory:

```bash
mkdir data
```

## Contract addresses

We used the only the contracts from the first 6.5 million blocks of the Ethereum blockchain.

You can download the list of the contract addresses from [here](http://honeybadger.uni.lu/datascience/addresses.txt).

For the following examples, we downloaded the addresses in the data directory:

```bash
cd data
wget http://honeybadger.uni.lu/datascience/addresses.txt
```

## Crawling the data

**The data is not included in this repository**. We downloaded the data from Etherscan API.
Since they limit their API to 5 requests per seconds, **the crawling process might take a long time**.

The three crawlers below can be executed in any order.

To crawl the source code:

- Crawl based on a file containing one contract address per line.
- Use `--update` if you want to add information to existing contracts (e.g. after bytecode crawl).

```bash
python honeypot_detection/crawl_source_code.py data/addresses.txt --update
```

To crawl the bytecode:

- Crawl based on a file containing one contract address per line.
- Use `--update` if you want to add information to existing contracts (e.g. after source code crawl).

```bash
python honeypot_detection/crawl_byte_code.py data/addresses.txt --update
```

To crawl both normal and internal transactions:

- Crawl based on a file containing one contract address per line.

```bash
python honeypot_detection/crawl_transactions.py data/addresses.txt
```

## Computing additional data

This will add several properties to contracts that have either source code or byte code crawled,
and the creation transaction crawled. Run it before computing the features.

```bash
python honeypot_detection/update_contract_from_creation_transaction.py
```

## Computing the features

For any of the three multiprocessing scripts below:

- Compute based on a file containing one contract address per line.
- Use `--processes` to define how many processes will be spawned.
- The database will be queried in read only mode.
- Results will be sent to an output file in csv format.

This multiprocessing script creates an intermediate file where each transaction is transformed into a fund flow case,
obtaining one sequence of fund flow cases per contract:

```bash
python honeypot_detection/create_fund_flow_case_sequences.py \
    --processes=2 \
    data/addresses.txt \
    data/fund_flow_case_sequences.csv 
```

This single process script compute the fund flow features (frequency of each case per contract):

```bash
python honeypot_detection/create_fund_flow_case_features.py \
    data/fund_flow_case_sequences.csv \
    data/features-fund_flow.csv 
```

This multiprocessing script creates the source code features:

```bash
python honeypot_detection/create_source_code_features.py \
    --processes=2 \
    data/addresses.txt \
    data/features-source_code.csv 
```

This multiprocessing script creates the aggregated transaction features (normal and internal):

```bash
python honeypot_detection/create_transaction_features.py \
    --processes=2 \
    data/addresses.txt \
    data/features-transactions.csv 
```

## Computing the labels

The labels are located in the folder ``honeybadger_labels``.
They were taken from [this repository](https://github.com/christoftorres/HoneyBadger)
that contains the code for the paper "The Art of The Scam: Demystifying Honeypots in Ethereum Smart Contracts".

First we need to load the labels from the csv files into the database:

```bash
python honeypot_detection/load_honey_badger_labels.py honeybadger_labels
```

Then propagate the labels to other contracts that share byte code with any labeled contract:

```bash
python honeypot_detection/propagate_honey_badger_labels.py
```

Then dump the labels into a file:

```bash
python honeypot_detection/dump_honey_badger_labels.py \
    data/addresses.txt \
    data/labels.csv
```

## Merging the dataset

The last step before the analysis is to merge all the dumped files into a dataset:

```bash
python honeypot_detection/merge_csv_files_by_contract_address.py \
    data/dataset.csv \
    data/labels.csv \
    data/features-fund_flow.csv \
    data/features-source_code.csv \
    data/features-transactions.csv
```

## Dictionaries for Categorical Variables

Many variables are one-hot-encoded in the dataset.
All the mappings between the categorical variable values and the assigned indices or IDs can be dumped in a directory:

```bash
python honeypot_detection/dump_dictionary.py data
```

To dump one dictionary in particular:

```bash
python honeypot_detection/dump_dictionary.py \
    --dictionary=honey_badger_labels \
    data/honey_badger_labels.pickle
```

All the dictionaries can be used in the following way:

```python
import pickle

with open("data/honey_badger_labels.pickle", "rb") as dictionary_file:
    dictionary = pickle.load(dictionary_file)

print(dictionary["id_to_value"][1])  # should print "Balance Disorder"
print(dictionary["value_to_id"]["Balance Disorder"])  # should print 1
```

## Machine Learning Experiments

The machine learning experiments may change every time the code for the feature extraction is changed.
The version of the experiments published in the paper is presented in the directory `paper_experiments`.
I uploaded the features extracted for the paper [here](https://drive.google.com/file/d/1eVeuZUVB7mcfBY4BoDEdjXXyZVXcD4ey/view?usp=sharing)
so you can run the experiments without waiting a long time until the data is crawled.
Extract the files on that directory and run the jupyter notebooks following the numeric order.
Additionally, note that the results on the paper may differ a bit because of the randomness involved on the experiments.

Or you can just see the results here on github:

- [Exploratory Analysis and Additional Pre-Processing](paper_experiments/1%20-%20Exploratory%20Analysis%20and%20Additional%20Pre-Processing.ipynb)
- [Most Relevant Features](paper_experiments/2%20-%20Most%20Relevant%20Features.ipynb)
- Experiment 1:
    - [Machine Learning Only Source Code Features](paper_experiments/3a%20-%20Machine%20Learning%20Only%20Source%20Code%20Features.ipynb)
    - [Machine Learning Only Fund Flow Features](paper_experiments/3b%20-%20Machine%20Learning%20Only%20Fund%20Flow%20Features.ipynb)
    - [Machine Learning Only Transaction Features](paper_experiments/3c%20-%20Machine%20Learning%20Only%20Transaction%20Features.ipynb)
    - [Machine Learning All the Features](paper_experiments/3d%20-%20Machine%20Learning%20All%20the%20Features.ipynb)
- [Experiment 2: Machine Learning One vs All](paper_experiments/4%20-%20Machine%20Learning%20One%20vs%20All.ipynb)
- [Experiment 3: Predict Probability](paper_experiments/5%20-%20Predict%20Probability.ipynb)