import io
import os
from pymongo import MongoClient
from surprise import SVD, KNNBaseline, dump, Reader, Dataset

client = MongoClient('mongodb://localhost:27017')
db = client.MovienderDB


def export_data_file():
    filePath = "C:\\Users\\Petros\\PycharmProjects\\LightFM_examples\\movielens\\dataset\\ml-1m\\ratings.dat"
    ratings = []

    with io.open(filePath, 'r', encoding='ISO-8859-1') as f:
        for line in f:
            line_split = line.split('::')
            ratings.append(line_split)

    cursor = list(db.Ratings.find())

    movies = list(db.Movies.find())
    movies_ids = [movie["movielens_id"] for movie in movies]

    for user in cursor:
        for movie_id in user["ratings"].keys():
            ratings.append([user['uid'], movie_id, user["ratings"][movie_id], "000000000"])

    with open("ratings.dat", 'w') as f:
        for rating in ratings:
            if rating[1] in movies_ids:
                uid = rating[0]
                movie_id = rating[1]
                rating_value = int(rating[2])
                timestamp = rating[3].strip()
                f.write(f"{uid}::{movie_id}::{rating_value}::{timestamp}\n")


def load_custom_dataset():
    file_path_large = "C:\\Users\\Petros\\PycharmProjects\\Moviender-API\\ratings.dat"

    reader_large = Reader(line_format='user item rating timestamp', sep='::')

    return Dataset.load_from_file(file_path=file_path_large, reader=reader_large)


def train_svd():
    data = load_custom_dataset()

    trainset = data.build_full_trainset()

    algo = SVD(n_factors=40, n_epochs=20, lr_all=0.005)
    algo.fit(trainset)

    # dump trained algorithm
    file_name = os.path.expanduser('TrainedModels\\trainedSVDAlgo.model')
    dump.dump(file_name=file_name, algo=algo)


def train_knn():
    # load custom dataset
    data = load_custom_dataset()
    trainset = data.build_full_trainset()

    # First, train the algorithm to compute the similarities between items
    sim_options = {'name': 'pearson_baseline', 'user_based': False}
    algo = KNNBaseline(sim_options=sim_options)
    algo.fit(trainset)

    # dump trained algorithm
    file_name = os.path.expanduser('TrainedModels\\trainedKNNBaseline.model')
    dump.dump(file_name=file_name, algo=algo)


def main():
    export_data_file()
    train_svd()
    train_knn()
    print("Training done!")


if __name__ == "__main__":
    main()
