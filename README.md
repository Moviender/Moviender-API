# <div align="center">Moviender API</div>

## Description
A restful API that was created as the backend of the [Moviender](https://github.com/Moviender/Moviender) application that was part of my thesis. Implemented with the [Fastapi](https://github.com/tiangolo/fastapi) framework for api capabilities, and pymongo for database management. It also uses the [Surprise](https://surpriselib.com/) library to generate in-app movie recommendations.

## Routers

### Users
The users router contains all the **GET** and **POST** requests that have to do with the user accounts and information.

**e.g.**

* GET `/initialized/{uid}` returns if the user exists in the database.
* POST `/user_genre_preference/` stores a user genre preferences to the database.

### Movies
The movies router contains all the **GET** and **POST** requests that have to do with the movie metadata, ratings and recommendations.

**e.g.**

* GET `/movie_details/{movie_id}` returns the metadata of a specific movie.
* POST `/rating/` stores a user rating for a specific movie.

### Friends
The friends router contains all the **GET** and **POST** requests that have to do with friend list and requests of the application.

**e.g.**

* GET `/friends/{uid}` returns the friend list of a specific user.
* POST `/friend_request/{uid}` stores the friend request of a user.

### Sessions
The sessions router contains all the **GET** and **POST** requests that have to do with recommendation sessions of the application.

**e.g.**

* GET `/session_results/{session_id}` returns the list with the recommendations for a specifc session.
* POST `/vote_in_session/{session_id}` stores the votes of a user for a specific sessions he/she is currently in.
