import numpy as np
import pandas as pd
from flask import Flask, request, jsonify, render_template,session
import pickle
from functools import reduce
from collections import defaultdict
import sys
from operator import itemgetter
import random
import json

global movie_name_data
global sorted_confidence


app = Flask(__name__)

app.secret_key = 'nonimportantkey'

#model = pickle.load(open('src/train/final_prediction.pickle', 'rb'))

@app.route('/')
def main():
    return render_template(
        "index.html"
    )

@app.route('/result', methods = ['POST'])
def result():
    if request.method == 'POST':

# Getting the initial values and the datasets

        global movie_name_data
        global sorted_confidence

        min_support = float(request.form['min_support'])
        min_confidence = float(request.form['min_confidence'])
        min_lift = float(request.form['min_lift'])
        min_length = float(request.form['min_length'])

        file_movies = request.files['file_movies']
        movie_name_data = pd.read_csv(file_movies,names=["MOVIE_ID","TITLE","GENRES"],header=1)
        file_ratings = request.files['file_ratings']
        all_ratings = pd.read_csv(file_ratings,names=["USER_ID","MOVIE_ID","RATING","TIMESTAMP"],header=1)

        all_ratings["FAVORABLE"]=all_ratings["RATING"]>3
        ratings=all_ratings[all_ratings["USER_ID"].isin(range(200))]
        favorable_ratings = ratings[ratings["FAVORABLE"]]

        favorable_reviews_by_users = dict((k, frozenset(v.values)) for k, v in favorable_ratings.groupby("USER_ID")["MOVIE_ID"])

        num_favorable_by_movie = ratings[["MOVIE_ID", "FAVORABLE"]].groupby("MOVIE_ID").sum()

        def find_frequent_itemsets(favorable_reviews_by_users, k_1_itemsets, min_support):
            counts = defaultdict(int)
            for user, reviews in favorable_reviews_by_users.items():
                for itemset in k_1_itemsets:
                    if itemset.issubset(reviews):
                        for other_reviewed_movie in reviews - itemset:
                            current_superset = itemset | frozenset((other_reviewed_movie,))
                            counts[current_superset] += 1
            return dict([(itemset, frequency) for itemset, frequency in counts.items() if frequency >= min_support])

        frequent_itemsets = {}  # itemsets are sorted by length 

        # k=1 candidates are the isbns with more than min_support favourable reviews
        frequent_itemsets[1] = dict((frozenset((movie_id,)), row["FAVORABLE"]) for movie_id, row in num_favorable_by_movie.iterrows() if row["FAVORABLE"] > min_support)

        for k in range(2, 20):
            # Generate candidates of length k, using the frequent itemsets of length k-1
            # Only store the frequent itemsets
            cur_frequent_itemsets = find_frequent_itemsets(favorable_reviews_by_users, frequent_itemsets[k-1],
                                                        min_support)
            if len(cur_frequent_itemsets) == 0:
                break
            else:
                frequent_itemsets[k] = cur_frequent_itemsets
        # We aren't interested in the itemsets of length 1, so remove those
        del frequent_itemsets[1]

        # Now we create the association rules. First, they are candidates until the confidence has been tested
        candidate_rules = []
        for itemset_length, itemset_counts in frequent_itemsets.items():
            for itemset in itemset_counts.keys():
                for conclusion in itemset:
                    premise = itemset - set((conclusion,))
                    candidate_rules.append((premise, conclusion))

        # Now, we compute the confidence of each of these rules. This is very similar to what we did in chapter 1
        correct_counts = defaultdict(int)
        incorrect_counts = defaultdict(int)
        for user, reviews in favorable_reviews_by_users.items():
            for candidate_rule in candidate_rules:
                premise, conclusion = candidate_rule
                if premise.issubset(reviews):
                    if conclusion in reviews:
                        correct_counts[candidate_rule] += 1
                    else:
                        incorrect_counts[candidate_rule] += 1

        rule_confidence = {candidate_rule: correct_counts[candidate_rule] / float(correct_counts[candidate_rule] + incorrect_counts[candidate_rule]) for candidate_rule in candidate_rules}

        rule_confidence = {rule: confidence for rule, confidence in rule_confidence.items() if confidence > min_confidence}

        sorted_confidence = sorted(rule_confidence.items(), key=itemgetter(1), reverse=True)

        return render_template('resultsform.html', movies_list=list(set(movie_name_data["TITLE"]))[:50])

@app.route('/recom', methods=["POST"])
def recom():

    global movie_name_data
    global sorted_confidence

    def get_movie_name(movie_id):
        title_object = movie_name_data[movie_name_data["MOVIE_ID"] == movie_id]["TITLE"]
        title = title_object.values[0]
        return title

    def recomendation(lista):
        for index in range(len(sorted_confidence)):
            (premise, conclusion) = sorted_confidence[index][0]
            premise_names = ", ".join(get_movie_name(idx) for idx in premise)
            my_list = premise_names.split(",")
            if sorted(lista)==sorted(my_list):
                conclusion_name = get_movie_name(conclusion)
                break

        return conclusion_name

    data = request.get_json()

    listatitulos=[]

    title = data["movie"]

    listatitulos.append(str(title))

    lista=                                                                                                   ['Star Wars: Episode IV - A New Hope (1977)', ' Seven (a.k.a. Se7en) (1995)', " Schindler's List (1993)"] 
    conclusion_name=recomendation(lista)

    temp = render_template(
        "ex.html", title=listatitulos,conclusion_name=conclusion_name,test=random.choice(movie_name_data["TITLE"].tolist()),
    )

    return json.dumps({
        "movie": temp
    })

@app.route('/about')
def about_page():
    return render_template('documentation.html')
        
