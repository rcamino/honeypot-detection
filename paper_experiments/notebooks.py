import pickle

import pandas as pd
import numpy as np

import matplotlib.pyplot as plt

from sklearn.metrics import roc_auc_score, confusion_matrix
from sklearn.preprocessing import MinMaxScaler

from sklearn.model_selection import KFold

from honeypot_detection.fund_flow_cases import convert_fund_flow_case_definition_to_instances


def load_dictionary(file_path):
    """
    Loads a categorical variable dictionary that was saved in pickle format.
    """
    with open(file_path, "rb") as dictionary_file:
        return pickle.load(dictionary_file)


def print_dimensions(target):
    """
    Prints the amount of rows and columns of the dataset.

    Arguments:
    target -- the pandas dataframe to print the dimensions
    """
    print("The dataset has {:d} rows and {:d} columns".format(*target.shape))


def fund_flow_case_ids_with_fixed_values(fund_flow_cases, **values):
    """
    Yield fund flow case IDs depending on the values of some fund flow case variables.
    If not values are defined, all the fund flow case IDs are yielded.
    If all the values are defined, only the corresponding fund flow case ID is yielded.

    Arguments:
    fund_flow_cases -- dictionary of the fund flow case values

    Keyword Arguments:
    values -- variable values to fix

    Example:
    fund_flow_case_columns_with_fixed_values(creation=True, error=False)
    fund_flow_case_columns_with_fixed_values(sender="creator")
    """
    for fund_flow_case in convert_fund_flow_case_definition_to_instances(defined=values):
        # yield fund_flow_cases["value_to_id"][fund_flow_case]  # updated version
        yield fund_flow_cases["name_to_index"][fund_flow_case]  # paper version


def fund_flow_case_columns_with_fixed_values(fund_flow_cases, **values):
    """
    Yield fund flow case columns depending on the values of some fund flow case variables.
    If not values are defined, all the fund flow case columns are yielded.
    If all the values are defined, only the corresponding fund flow case columns is yielded.

    Arguments:
    fund_flow_cases -- dictionary of the fund flow case values

    Keyword Arguments:
    values -- variable values to fix

    Example:
    fund_flow_case_columns_with_fixed_values(creation=True, error=False)
    fund_flow_case_columns_with_fixed_values(sender="creator")
    """
    for fund_flow_case_id in fund_flow_case_ids_with_fixed_values(fund_flow_cases, **values):
        # yield "fund_flow_case_{:d}_frequency".format(fund_flow_case_id)  # updated version
        yield "symbol_{:d}".format(fund_flow_case_id)  # paper version


def fund_flow_case_columns_accumulated_frequency(fund_flow_cases, target, **values):
    """
    Accumulate the frequency of fund flow cases per contract depending on the values of some fund flow case variables.
    If not values are defined, all the fund flow case frequencies will be added,
    and they should add up to one on each contract.
    If all the values are defined, only the corresponding fund flow case frequency is collected per contract.

    Arguments:
    fund_flow_cases -- dictionary of the fund flow case values
    target -- the pandas dataframe from which the frequencies are calculated

    Keyword Arguments:
    values -- variable values to fix

    Example:
    fund_flow_case_columns_with_fixed_values(df, creation=True, error=False)
    fund_flow_case_columns_with_fixed_values(df, sender="creator")
    """
    accumulated = pd.Series(np.zeros(len(target)))
    for column in fund_flow_case_columns_with_fixed_values(fund_flow_cases, **values):
        if column in target:  # maybe it was already removed
            accumulated += target[column]
    return accumulated


def filter_with_prefixes(value, prefixes):
    """
    Returns true if at least one of the prefixes exists in the value.

    Arguments:
    value -- string to validate
    prefixes -- list of string prefixes to validate at the beginning of the value
    """
    for prefix in prefixes:
        if value.startswith(prefix):
            return False
    return True


def extract_experiment_data(target, filter_feature_categories=None):
    """
    Extracts a tuple of data for machine learning experiments from a dataset:
    - address list
    - feature 2-dimensional array
    - binary label array
    - multi-class label array
    - scikit-learn scaler
    - list of feature names corresponding to the feature matrix

    Arguments:
    target -- pandas dataframe to extract the data
    feature_categories -- list containing "transaction", "source code" or "fund flow";
        if None, all feature categories will be used
    """
    features_metadata = pd.read_csv("dataset-metadata.csv")

    if filter_feature_categories is not None:
        features_metadata = features_metadata[features_metadata.category.isin(filter_feature_categories)]

    columns_to_scale = []
    other_columns = []

    target_columns = set(target.columns)

    for _, row in features_metadata.iterrows():
        if row["feature"] in target_columns:  # in case the feature was filtered out
            if row["scale"] == 1:
                columns_to_scale.append(row["feature"])
            else:
                other_columns.append(row["feature"])

    if len(columns_to_scale) > 0:
        scaler = MinMaxScaler()
        features_scaled = scaler.fit_transform(target[columns_to_scale].values)
    else:
        scaler = None
        features_scaled = None

    if len(other_columns) > 0:
        features_others = target[other_columns].values
    else:
        features_others = None

    feature_names = columns_to_scale + other_columns

    if len(feature_names) == 0:
        raise Exception("At least one column should be used.")

    if features_scaled is not None and features_others is not None:
        features = np.concatenate((features_scaled, features_others), axis=1)
    elif features_scaled is None:
        features = features_others
    elif features_others is None:
        features = features_scaled
    else:
        raise Exception("This should not happen.")

    if scaler is not None:
        print("Scaled columns:")
        for column, min_value, max_value in zip(columns_to_scale, scaler.data_min_, scaler.data_max_):
            print("{:s}: [{:.0f}, {:.0f}]".format(column, min_value, max_value))
        print()

    addresses = target.contract_address

    labels_binary = target.contract_is_honeypot.values
    labels_multi = target.contract_label_index.values

    print("Extracted values:")
    print("addresses", addresses.shape)
    print("features", features.shape)
    print("labels_binary", labels_binary.shape)
    print("labels_multi", labels_multi.shape)

    return addresses, features, labels_binary, labels_multi, scaler, feature_names


def compute_scale_pos_weight(labels_binary):
    """
    Calculate the scale_pos_weight parameter for XGBoost when the dataset is imbalanced.

    See: https://xgboost.readthedocs.io/en/latest/parameter.html

    Arguments:
    labels_binary -- binary label array
    """
    return (1 - labels_binary).sum() / labels_binary.sum()


def k_fold(features, n_splits=10, random_state=None):
    """
    Creates a cross validation iterator that yields (train_index, test_index) n_splits times.

    Arguments:
    features -- feature 2-dimensional array
    n_splits -- number of parts in which the dataset should be splitted
    random_state -- numpy random number generator state or seed
    """
    folds = KFold(n_splits=n_splits, random_state=random_state, shuffle=True)
    return folds.split(features)


def compute_metrics(labels, predictions):
    """
    Computes the ROC AUC score and the four metrics of the confusion matrix tn, fp, fn and tp.

    Arguments:
    labels -- binary label array
    predictions -- binary prediction array
    """
    score = roc_auc_score(labels, predictions)
    tn, fp, fn, tp = confusion_matrix(labels, predictions).ravel()
    return score, tn, fp, fn, tp


def train_and_test_fold(model, features, labels_binary, train_index, test_index):
    """
    Trains an XGBoost model instance with the indicated fold from the feature matrix.
    Then calculates and returns the train and test metrics.

    Arguments:
    model --
    features -- feature 2-dimensional array
    labels_binary -- binary label array
    train_index -- array with row indices for training
    test_index -- array with row indices for testing
    """
    model.fit(features[train_index], labels_binary[train_index])
    train_metrics = compute_metrics(labels_binary[train_index], model.predict(features[train_index]))
    test_metrics = compute_metrics(labels_binary[test_index], model.predict(features[test_index]))
    return train_metrics, test_metrics


def print_metrics(name, metrics):
    """
    Arguments:
    name -- string to show at the beggining of the metric
    metrics -- tuple with the form (score, tn, fp, fn, tp)
    """
    score, tn, fp, fn, tp = metrics
    print("{} ROC AUC {:.03f} TN {: 5d} FP {: 5d} FN {: 5d} TP {: 5d}".format(name.ljust(5), score, tn, fp, fn, tp))


def train_test_folds(features, labels_binary, cv_iterator, model_factory):
    """
    Creates and trains an XGBoost model instance per fold from the feature matrix.
    Train and test metrics are printed per fold.
    The mean and std of the ROC AUC is printed at the end.
    Returns all the trained models.

    Arguments:
    features -- feature 2-dimensional array
    labels_binary -- binary label array
    cv_iterator -- iterator that yields (train_index, test_index)
    model_factory -- callable that creates a model instance
    """
    train_scores = []
    test_scores = []
    models = []
    for train_index, test_index in cv_iterator:
        model = model_factory()
        train_metrics, test_metrics = train_and_test_fold(model, features, labels_binary, train_index, test_index)

        train_scores.append(train_metrics[0])
        test_scores.append(test_metrics[0])
        models.append(model)

        print_metrics("train", train_metrics)
        print_metrics("test", test_metrics)
        print("train score - test score = {:.03f}".format(train_metrics[0] - test_metrics[0]))
        print()

    print("train: {:.03f} +- {:.03f} test: {:.03f} +- {:.03f}".format(
        np.mean(train_scores), np.std(train_scores), np.mean(test_scores), np.std(test_scores)))
    print()

    return models


def compute_average_feature_importance(features, models, importance_type=None):
    """
    See: https://xgboost.readthedocs.io/en/latest/python/python_api.html#xgboost.Booster.get_score

    Arguments:
    features -- feature 2-dimensional array
    models -- list of trained model instances
    importance_type -- name of the importance to calculate
    """
    num_features = features.shape[1]
    feature_importance = np.zeros(num_features)
    for model in models:
        if importance_type is None:
            feature_importance += model.feature_importances_
        else:
            feature_importance_fold = np.zeros(num_features)
            feature_importance_fold_dict = model.get_booster().get_score(importance_type=importance_type)
            for feature_generated_name, feature_importance in feature_importance_fold_dict.items():
                feature_index = int(feature_generated_name[1:])
                feature_importance_fold[feature_index] = feature_importance
            feature_importance += feature_importance_fold
    feature_importance /= len(models)
    return feature_importance


def create_feature_importance_table(feature_names, feature_importance, size=20):
    """
    Arguments:
    feature_names -- list of feature names corresponding to the feature matrix
    feature_importance -- array of feature importance values
    size -- maximum amount of features to show
    """
    indices = np.argsort(feature_importance)
    indices = indices[-size:]
    indices = indices[::-1]

    return pd.DataFrame({
        "Feature": [feature_names[i] for i in indices],
        "Importance": feature_importance[indices]
    })


def plot_feature_importance(feature_names, feature_importance, size=20):
    """
    Arguments:
    feature_names -- list of feature names corresponding to the feature matrix
    feature_importance -- array of feature importance values
    size -- maximum amount of features to show
    """
    indices = np.argsort(feature_importance)[-size:]

    plt.figure(figsize=(10, 10))
    plt.title("Feature Importance")
    plt.barh(np.arange(len(indices)), feature_importance[indices])
    plt.yticks(range(len(indices)), [feature_names[i] for i in indices])
    plt.xlabel("Relative Importance")
    plt.tight_layout()
    plt.show()
