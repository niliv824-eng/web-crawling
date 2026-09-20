# Laptop Data Mining & Price Prediction

## Overview

This project focuses on analyzing laptop data collected from Amazon.de and applying data mining and machine learning techniques to predict laptop prices.

The main goal of the project is to explore whether laptop specifications such as CPU, GPU, RAM, storage, screen size, resolution, operating system, and other features can be used to predict the price of a laptop.

## Project Workflow

The project was completed in several main stages:

### 1. Data Collection

Laptop information was collected from **Amazon.de**.

The dataset contains different laptop specifications, including:

* Brand
* CPU
* GPU
* RAM
* Storage
* Screen size
* Resolution
* Operating system
* Keyboard
* Gaming capability
* Touchscreen
* Rating
* Number of reviews
* Price

### 2. Data Cleaning

After collecting the data, the dataset was cleaned and prepared for analysis.

The preprocessing steps included:

* Removing irrelevant and non-laptop products
* Cleaning brand names
* Correcting inconsistent values
* Handling missing values
* Checking numerical features
* Checking potential outliers
* Converting binary features into numerical values
* Preparing categorical features for machine learning

### 3. Exploratory Data Analysis

The dataset was analyzed to understand the relationships between laptop specifications and their prices.

Different numerical and categorical features were investigated to identify patterns and important factors related to laptop prices.

### 4. Feature Engineering and Feature Selection

Several feature selection techniques were tested to identify the most useful features for price prediction.

The techniques included:

* Correlation Analysis
* Random Forest Feature Importance
* Mutual Information
* SelectKBest
* Recursive Feature Elimination (RFE)

Different numbers of selected features were also tested and compared.

### 5. Machine Learning

Several machine learning approaches were used for laptop price prediction, including:

* Random Forest Regressor
* CatBoost Regressor

The models were evaluated using:

* R² Score
* Mean Absolute Error (MAE)
* Root Mean Squared Error (RMSE)

Different feature subsets were tested to investigate whether feature selection could improve the prediction performance.

### 6. Clustering

K-Means clustering was also explored to group laptops based on their technical specifications.

The purpose of clustering was to identify groups of laptops with similar characteristics and investigate whether these groups were related to different price ranges.

### 7. Association Rule Mining

Association rule mining was considered as another data mining technique for discovering relationships between laptop characteristics.

For example, combinations of specifications such as RAM, GPU, and gaming capability can be analyzed to identify patterns associated with different price categories.

## Results

The experiments showed that predicting laptop prices from the available features is a challenging task.

Although feature selection and different machine learning algorithms improved the results to some extent, the models did not achieve a very high R² score.

The best Random Forest experiment reached approximately **51% R²** with a selected subset of features.

This indicates that the available laptop specifications can explain part of the variation in prices, but they are not sufficient to accurately predict all price differences.

Possible reasons include:

* Limited dataset size
* Large variation in laptop prices
* Brand effects
* Product-specific factors
* Market and seller differences
* Features that are not available in the dataset

## Conclusion

This project demonstrates a complete data mining workflow, starting from real-world data collection from Amazon.de and continuing through data cleaning, exploratory analysis, feature selection, machine learning, clustering, and association rule mining.

The results also show that achieving a high prediction accuracy is not always possible with a limited real-world dataset. The experiments provide useful insight into the relationship between laptop specifications and prices and demonstrate the practical challenges of machine learning on real-world e-commerce data.

## Technologies

* Python
* Pandas
* NumPy
* Scikit-learn
* CatBoost
* Matplotlib
* Seaborn
* Jupyter Notebook

## Dataset

The dataset was collected from Amazon.de for educational and data mining purposes.
