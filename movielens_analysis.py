import os
import re
import json

from collections import Counter
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

import pytest


class Ratings:
    def __init__(self, ratings_path, movies_path):
        self.path = ratings_path
        self.data = []

        with open(movies_path, "r", encoding="utf-8") as f:
            header = f.readline().strip().lower()
            if "movieid" not in header or "title" not in header or "genres" not in header:
                raise ValueError(f"Неверная структура файла movies: {header}")

        with open(ratings_path, "r", encoding="utf-8") as f:
            header = f.readline().strip().lower()
            if "userid" not in header or "movieid" not in header or "rating" not in header:
                raise ValueError(f"Неверная структура файла ratings: {header}")
        
        movies = {}
        with open(movies_path, "r", encoding="utf-8") as f:
            next(f)
            for i, line in enumerate(f):
                if i >= 1000:
                    break

                parts = re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', line.strip())
                movie_id = parts[0]
                title = parts[1].strip('"')
                genres = parts[2].split("|")
                movies[movie_id] = [title, genres]

        with open(ratings_path, "r", encoding="utf-8") as f:
            next(f)
            for line in f:
                parts = line.strip().split(",")

                if parts[1] not in movies:
                    continue

                movie_info = movies[parts[1]]
                parts.append(movie_info[0])
                parts.append(movie_info[1])
                self.data.append(parts)

    def _group_ratings_by(self, key_index):
        dic = {}
        for parts in self.data:
            dic.setdefault(parts[key_index], []).append(float(parts[2]))
        return dic

    def _count_by(self, key_index):
        res = []
        for parts in self.data:
            res.append(parts[key_index])
        return Counter(res)

    def _stat_by(self, key_index, metric):
        dic = self._group_ratings_by(key_index)
        if metric == "average":
            return {k: round(sum(v) / len(v), 2) for k, v in dic.items()}
        elif metric == "median":
            return {
                k: (
                    sorted(v)[len(v) // 2]
                    if len(v) % 2 == 1
                    else round(
                        (sorted(v)[len(v) // 2] + sorted(v)[len(v) // 2 - 1]) / 2, 2
                    )
                )
                for k, v in dic.items()
            }
        else:
            raise ValueError(
                "Function expects 'average' or 'median' as second argument"
            )

    def _controversial(self, key_index):
        dic = self._group_ratings_by(key_index)
        for k, v in dic.items():
            mean = sum(v) / len(v)
            dic[k] = round(sum((x - mean) ** 2 for x in v) / len(v), 2)
        return dic

    class Movies:
        def __init__(self, ratings):
            self.ratings = ratings
            self.path = ratings.path
            self.key_index = 4

        def dist_by_year(self):
            res = []
            for parts in self.ratings.data:
                res.append(datetime.fromtimestamp(int(parts[3])).year)
            return dict(sorted(Counter(res).items()))

        def dist_by_rating(self):
            res = []
            for parts in self.ratings.data:
                res.append(parts[2])
            return dict(sorted(Counter(res).items()))

        def top_by_num_of_ratings(self, n):
            dic = self.ratings._count_by(self.key_index)
            return dict(sorted(dic.items(), key=lambda x: x[1], reverse=True)[:n])

        def top_by_ratings(self, n, metric="average"):
            dic = self.ratings._stat_by(self.key_index, metric)
            return dict(sorted(dic.items(), key=lambda x: x[1], reverse=True)[:n])

        def top_controversial(self, n):
            dic = self.ratings._controversial(self.key_index)
            return dict(sorted(dic.items(), key=lambda x: x[1], reverse=True)[:n])

    class Users(Movies):
        def __init__(self, ratings):
            super().__init__(ratings)
            self.key_index = 0
    
    def get_count(self):
        return len(self.data)


class Movies:
    def __init__(self, path_to_the_file):
        self.path = path_to_the_file
        self.movies = []

        with open(self.path, "r", encoding="utf-8") as file:
            header = file.readline().strip().lower()
            if "movieid" not in header or "title" not in header or "genres" not in header:
                raise ValueError(f"Неверная структура файла movies: {header}")

        with open(self.path, "r", encoding="utf-8") as file:
            next(file)

            for i, line in enumerate(file):
                if i >= 1000:
                    break
                line = line.rstrip("\n")
                match = re.search(r'"(.*?)"', line)
                if match:
                    title = match.group(1).replace(",", "\t")
                    line = line.replace(match.group(1), title)

                parts = line.split(",")

                movie = {
                    "movieId": int(parts[0]),
                    "title": parts[1].replace("\t", ",").strip('"'),
                    "genres": parts[2].split("|")
                }

                self.movies.append(movie)

    def dist_by_release(self):
        year_pattern = re.compile(r"\((\d{4})\)\s*$")
        year_counts = Counter()

        for movie in self.movies:
            match = year_pattern.search(movie["title"])

            if match:
                year_counts[int(match.group(1))] += 1

        return dict(year_counts.most_common())
    def dist_by_genres(self):

        genre_counts = Counter()

        for movie in self.movies:
            for genre in movie["genres"]:
                genre_counts[genre] += 1

        return dict(genre_counts.most_common())

    def movies_by_genre(self, genre, n=None):
        result = []
        for movie in self.movies:
            if genre in movie["genres"]:
                result.append(movie["title"])
        result = sorted(result)
        return result if n is None else result[:n]

    def most_genres(self, n):
        movies = {}

        for movie in self.movies:
            movies[movie["title"]] = len(movie["genres"])

        sorted_movies = sorted(
            movies.items(),
            key=lambda item: (-item[1], item[0])
        )

        return dict(sorted_movies[:n])

    def longest_title(self):
        return max(self.movies, key=lambda movie: len(movie["title"]))["title"]
    
    def get_count(self):
        return len(self.movies)


class Tags:

    def __init__(self, path_to_the_file):

        self.path = path_to_the_file
        self.tags = []

        with open(self.path, "r", encoding="utf-8") as file:
            header = file.readline().strip().lower()
            if "userid" not in header or "movieid" not in header or "tag" not in header:
                raise ValueError(f"Неверная структура файла tags: {header}")

        with open(self.path, "r", encoding="utf-8") as file:
            next(file)

            for line in file:
                line = line.rstrip("\n")

                first = line.find(",")
                second = line.find(",", first + 1)
                last = line.rfind(",")

                user_id = int(line[:first])
                movie_id = int(line[first + 1:second])
                tag = line[second + 1:last].strip('"')
                timestamp = int(line[last + 1:])

                self.tags.append({
                    "userId": user_id,
                    "movieId": movie_id,
                    "tag": tag,
                    "timestamp": timestamp
                })


    def most_words(self, n):
        unique_tags = set(item["tag"] for item in self.tags)

        words = {}

        for tag in unique_tags:
            words[tag] = len(tag.split())

        sorted_tags = sorted(
            words.items(),
            key=lambda item: (-item[1], item[0])
        )

        return dict(sorted_tags[:n])

    def longest(self, n):
        unique_tags = set(item["tag"] for item in self.tags)

        sorted_tags = sorted(unique_tags, key=lambda tag: (-len(tag), tag))

        return sorted_tags[:n]

    def most_words_and_longest(self, n):
        most_words = set(self.most_words(n).keys())
        longest = set(self.longest(n))

        return sorted(list(most_words & longest))

    def most_popular(self, n):
        counter = Counter()

        for item in self.tags:
            counter[item["tag"]] += 1

        return dict(counter.most_common(n))

    def tags_with(self, word):
        result = set()

        for item in self.tags:
            if word in item["tag"].split():
                result.add(item["tag"])

        return sorted(result)

    def movies_with_tag(self, word):
        movies = set()

        for item in self.tags:
            if word in item["tag"]:
                movies.add(item["movieId"])
        return len(movies)
    def most_active_user(self):
        counter = Counter()

        for item in self.tags:
            counter[item["userId"]] += 1

        return counter.most_common(1)[0]

    def get_count(self):
        return len(self.tags)

class Links:
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, path_to_the_file, movies_path=None):
        self.path_to_the_file = path_to_the_file
        titles_by_id = self._read_titles(movies_path or self._default_movies_path(path_to_the_file))
        self.data = self._read_links(path_to_the_file, titles_by_id)
        self.links = self.data  
        self.imdb_cache = self._load_imdb_cache(path_to_the_file)

    @staticmethod
    def _default_movies_path(path_to_the_file):
        return os.path.join(
            os.path.dirname(os.path.abspath(path_to_the_file)), "movies.csv"
        )

    @staticmethod
    def _read_titles(movies_path):
        titles = {}
        if not movies_path or not os.path.exists(movies_path):
            return titles
        try:
            with open(movies_path, "r", encoding="utf-8", newline="") as f:
                next(f) 

                for i, line in enumerate(f):
                    if i >= 1000: 
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        movie_id_str, rest = line.split(",", 1)
                        title_and_genres = rest.rsplit(",", 1)
                        title = title_and_genres[0]
                        if title.startswith('"') and title.endswith('"'):
                            title = title[1:-1]
                        titles[int(movie_id_str)] = title
                    except ValueError:
                        continue
                    
        except OSError:
            return {}
        
        return titles

    @staticmethod
    def _load_imdb_cache(path_to_the_file):
        cache_path = os.path.join(
            os.path.dirname(os.path.abspath(path_to_the_file)), "imdb_cache.json"
        )
        if not os.path.exists(cache_path):
            return {}
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                raw_cache = json.load(f)
            return {int(movie_id): data for movie_id, data in raw_cache.items()}
        except (json.JSONDecodeError, ValueError, OSError):
            return {}

    @staticmethod
    def _read_links(path_to_the_file, titles_by_id):
        if not os.path.exists(path_to_the_file):
            raise FileNotFoundError(f"links file not found: {path_to_the_file}")
        data = []
        with open(path_to_the_file, 'r', encoding='utf-8', newline='') as f:
            header = f.readline().strip().lower()
            for i, line in enumerate(f):
                if i >= 1000:  
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    movie_id_str, imdb_id, tmdb_id = line.split(',')
                    movie_id = int(movie_id_str)
                except ValueError as e:
                    raise ValueError(f"could not parse links.csv row {line!r}: {e}")

                data.append({
                    "movieId": movie_id,
                    "imdbId": imdb_id.strip(),
                    "tmdbId": tmdb_id.strip(),
                    "title": titles_by_id.get(movie_id, f"Movie {movie_id}"),
                })
        return data

    def _link_by_movie_id(self, movie_id):
        """Returns the {"movieId", "imdbId", "tmdbId", "title"} dict for a
        given movieId, or None if it is not present in links.csv."""
        for row in self.data:
            if row["movieId"] == movie_id:
                return row
        return None

    @staticmethod
    def _imdb_id_to_url(imdb_id):
        imdb_id = str(imdb_id).strip()
        return f"https://www.imdb.com/title/tt{imdb_id}/"

    def _get_imdb_data(self, movie_id):
        if movie_id not in self.imdb_cache:
            link = self._link_by_movie_id(movie_id)
            if link is None:
                raise ValueError(f"movieId {movie_id} not found in links data")
            self.imdb_cache[movie_id] = self._scrape_imdb(link["imdbId"])
        return self.imdb_cache[movie_id]

    def _scrape_imdb(self, imdb_id):
        result = {
            "Director": None,
            "Budget": None,
            "Cumulative Worldwide Gross": None,
            "Runtime": None,
        }
        url = Links._imdb_id_to_url(imdb_id)
        try:
            response = requests.get(url, headers=Links._HEADERS, timeout=15)
            response.raise_for_status()
        except Exception as e:
            raise ConnectionError(f"could not fetch {url}: {e}")

        soup = BeautifulSoup(response.text, "html.parser")

        ld_json_tag = soup.find("script", {"type": "application/ld+json"})
        if ld_json_tag and ld_json_tag.string:
            try:
                ld_data = json.loads(ld_json_tag.string)
                directors = ld_data.get("director")
                if directors:
                    if isinstance(directors, dict):
                        directors = [directors]
                    names = [d.get("name") for d in directors if d.get("name")]
                    if names:
                        result["Director"] = ", ".join(names)
                duration = ld_data.get("duration") 
                if duration:
                    result["Runtime"] = Links._iso8601_duration_to_minutes(duration)
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass

        if result["Director"] is None:
            try:
                for item in soup.select("li.ipc-metadata-list__item"):
                    label_el = item.select_one("span.ipc-metadata-list-item__label")
                    if label_el and "Director" in label_el.get_text():
                        names = [a.get_text(strip=True) for a in item.select("a")]
                        if names:
                            result["Director"] = ", ".join(names)
                        break
            except Exception:
                pass

        try:
            for item in soup.select("li.ipc-metadata-list__item"):
                label_el = item.select_one("span.ipc-metadata-list-item__label")
                if not label_el:
                    continue
                label_text = label_el.get_text(strip=True)
                value_el = item.select_one(
                    "span.ipc-metadata-list-item__list-content-item"
                )
                if not value_el:
                    continue
                value_text = value_el.get_text(strip=True)

                if label_text == "Budget":
                    result["Budget"] = Links._extract_money(value_text)
                elif label_text in ("Cumulative Worldwide Gross", "Gross worldwide"):
                    result["Cumulative Worldwide Gross"] = Links._extract_money(value_text)
                elif label_text == "Runtime":
                    result["Runtime"] = Links._extract_runtime_minutes(value_text)
        except Exception:
            pass
        Links._wait_seconds(1)

        return result

    @staticmethod
    def _wait_seconds(seconds):
        deadline = datetime.now() + timedelta(seconds=seconds)
        while datetime.now() < deadline:
            pass

    @staticmethod
    def _iso8601_duration_to_minutes(duration):
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", duration)
        if not match:
            return None
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        return hours * 60 + minutes

    @staticmethod
    def _extract_money(text):
        digits = re.sub(r"[^\d]", "", text.split("(")[0])
        return int(digits) if digits else None

    @staticmethod
    def _extract_runtime_minutes(text):
        hours = re.search(r"(\d+)\s*h", text)
        minutes = re.search(r"(\d+)\s*m", text)
        if hours or minutes:
            total = int(hours.group(1)) * 60 if hours else 0
            total += int(minutes.group(1)) if minutes else 0
            return total
        plain_minutes = re.search(r"(\d+)", text)
        return int(plain_minutes.group(1)) if plain_minutes else None

    def get_imdb(self, list_of_movies, list_of_fields):
        if not isinstance(list_of_movies, list):
            raise TypeError("list_of_movies must be a list")
        if not isinstance(list_of_fields, list):
            raise TypeError("list_of_fields must be a list")
            
        result = []
        for movie_id in sorted(list_of_movies, reverse=True):
            try:
                data = self._get_imdb_data(int(movie_id))
            except ValueError:
                continue
            except ConnectionError as e:
                raise RuntimeError(f"HTTP request failed during IMDB scraping for movie {movie_id}: {e}")
            except Exception as e:
                raise RuntimeError(f"Unexpected error for movieId {movie_id}: {e}")
            row = [movie_id] + [data.get(field) for field in list_of_fields]
            result.append(row)
        return result

    def top_directors(self, n):
        if not isinstance(n, int):
            raise TypeError("n must be an integer")
        if n < 0:
            raise ValueError("n must be a positive integer")
        movie_ids = [row["movieId"] for row in self.data[:1000]]
        rows = self.get_imdb(movie_ids, ["Director"])
        director_counts = Counter()
        for _, director in rows:
            if not director:
                continue
            for single_director in director.split(", "):
                director_counts[single_director] += 1
        top = dict(
            sorted(director_counts.items(), key=lambda item: item[1], reverse=True)[:n]
        )
        return top

    def average_budget_by_director(self, n):
        if not isinstance(n, int):
            raise TypeError("n must be an integer")
        if n < 0:
            raise ValueError("n must be a positive integer")

        movie_ids = [row["movieId"] for row in self.data[:1000]]
        rows = self.get_imdb(movie_ids, ["Director", "Budget"])

        budgets_by_director = {}
        for _, director, budget in rows:
            if not director or budget is None:
                continue
            for single_director in director.split(", "):
                budgets_by_director.setdefault(single_director, []).append(budget)

        averages = {
            director: round(sum(budgets) / len(budgets), 2)
            for director, budgets in budgets_by_director.items()
        }

        return dict(
            sorted(averages.items(), key=lambda item: item[1], reverse=True)[:n]
        )

    def most_expensive(self, n):
        return self._top_n_numeric_field(fields=["Budget"], value_index=1, n=n)

    def most_profitable(self, n):
        movie_ids = [row["movieId"] for row in self.data[:1000]]
        rows = self.get_imdb(movie_ids, ["Budget", "Cumulative Worldwide Gross"])
        titles_by_id = self._titles_by_movie_id()
        profits = {}
        for movie_id, budget, gross in rows:
            if budget is None or gross is None:
                continue
            title = titles_by_id[movie_id]
            profits[title] = gross - budget

        return dict(
            sorted(profits.items(), key=lambda item: item[1], reverse=True)[:n]
        )

    def longest(self, n):
        return self._top_n_numeric_field(fields=["Runtime"], value_index=1, n=n)

    def top_cost_per_minute(self, n):
        movie_ids = [row["movieId"] for row in self.data[:1000]]
        rows = self.get_imdb(movie_ids, ["Budget", "Runtime"])
        titles_by_id = self._titles_by_movie_id()
        costs = {}
        for movie_id, budget, runtime in rows:
            if budget is None or not runtime:
                continue
            title = titles_by_id[movie_id]
            costs[title] = round(budget / runtime, 2)
        return dict(
            sorted(costs.items(), key=lambda item: item[1], reverse=True)[:n]
        )

    def _top_n_numeric_field(self, fields, value_index, n):
        movie_ids = [row["movieId"] for row in self.data[:1000]]
        rows = self.get_imdb(movie_ids, fields)
        titles_by_id = self._titles_by_movie_id()

        values = {}
        for row in rows:
            movie_id = row[0]
            value = row[value_index]
            if value is None:
                continue
            title = titles_by_id[movie_id]
            values[title] = value

        return dict(
            sorted(values.items(), key=lambda item: item[1], reverse=True)[:n]
        )

    def _titles_by_movie_id(self):
        return {row["movieId"]: row["title"] for row in self.data[:1000]}
    
    def get_count(self):
        return len(self.data)

def try_wrong_file(class_name, path):
    try:
        if class_name.lower() == "links":
            Links(path)
        elif class_name.lower() == "movies":
            Movies(path)
        elif class_name.lower() == "tags":
            Tags(path)
        elif class_name.lower() == "ratings":
            Ratings(path, path)
        return "Ошибка ValueError НЕ была выброшена!"
    except ValueError as e:
        return str(e)  # Перехватываем и превращаем в строку
    except Exception as e:
        return f"Неожиданное исключение: {type(e).__name__}: {e}"


def try_missing_file(class_name, path):
    try:
        if class_name.lower() == "links":
            Links(path)
        elif class_name.lower() == "movies":
            Movies(path)
        elif class_name.lower() == "tags":
            Tags(path)
        elif class_name.lower() == "ratings":
            Ratings(path, path)
        return "Ошибка FileNotFoundError НЕ была выброшена!"
    except FileNotFoundError as e:
        return str(e)  # Перехватываем и превращаем в строку
    except Exception as e:
        return f"Неожиданное исключение: {type(e).__name__}: {e}"

class Tests:
    def test_dist_by_release(self):
        movies = Movies("movies.csv")
        result = movies.dist_by_release()

        assert isinstance(result, dict)
        assert all(isinstance(key, int) for key in result.keys())
        assert all(isinstance(value, int) for value in result.values())

        values = list(result.values())
        assert values == sorted(values, reverse=True)

    def test_dist_by_genres(self):
        movies = Movies("movies.csv")
        result = movies.dist_by_genres()

        assert isinstance(result, dict)
        assert all(isinstance(key, str) for key in result.keys())
        assert all(isinstance(value, int) for value in result.values())

        values = list(result.values())
        assert values == sorted(values, reverse=True)
    def test_movies_by_genre(self):
        movies = Movies("movies.csv")
        result = movies.movies_by_genre("Comedy")

        assert isinstance(result, list)
        assert all(isinstance(movie, str) for movie in result)
        assert result == sorted(result)
    def test_movies_by_genre_limit(self):
        movies = Movies("movies.csv")
        result = movies.movies_by_genre("Comedy", 10)

        assert isinstance(result, list)
        assert len(result) <= 10
        assert all(isinstance(movie, str) for movie in result)
        assert result == sorted(result)

    def test_most_genres(self):
        movies = Movies("movies.csv")
        result = movies.most_genres(10)

        assert isinstance(result, dict)
        assert all(isinstance(key, str) for key in result.keys())
        assert all(isinstance(value, int) for value in result.values())

        values = list(result.values())
        assert values == sorted(values, reverse=True)

    def test_most_words(self):
        tags = Tags("tags.csv")
        result = tags.most_words(10)

        assert isinstance(result, dict)
        assert all(isinstance(key, str) for key in result.keys())
        assert all(isinstance(value, int) for value in result.values())

        values = list(result.values())
        assert values == sorted(values, reverse=True)

    def test_longest(self):
        tags = Tags("tags.csv")
        result = tags.longest(10)

        assert isinstance(result, list)
        assert all(isinstance(tag, str) for tag in result)

        lengths = [len(tag) for tag in result]
        assert lengths == sorted(lengths, reverse=True)

    def test_most_words_and_longest(self):
        tags = Tags("tags.csv")
        result = tags.most_words_and_longest(10)

        assert isinstance(result, list)
        assert all(isinstance(tag, str) for tag in result)

    def test_most_popular(self):
        tags = Tags("tags.csv")
        result = tags.most_popular(10)

        assert isinstance(result, dict)
        assert all(isinstance(key, str) for key in result.keys())
        assert all(isinstance(value, int) for value in result.values())

        values = list(result.values())
        assert values == sorted(values, reverse=True)

    def test_tags_with(self):
        tags = Tags("tags.csv")
        result = tags.tags_with("comedy")

        assert isinstance(result, list)
        assert all(isinstance(tag, str) for tag in result)
        assert result == sorted(result)

    def test_longest_title(self):
        movies = Movies("movies.csv")
        result = movies.longest_title()
        assert isinstance(result, str)

    def test_movies_with_tag(self):
        tags = Tags("tags.csv")
        result = tags.movies_with_tag("comedy")
        assert isinstance(result, int)
    def test_most_active_user(self):
        tags = Tags("tags.csv")
        result = tags.most_active_user()

        assert isinstance(result, tuple)
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)

    #Links tests
    _FAKE_IMDB = {
        "0114709": {"Director": "John Lasseter", "Budget": 30000000,
                    "Cumulative Worldwide Gross": 373554033, "Runtime": 81},
        "0113497": {"Director": "Joe Johnston", "Budget": 65000000,
                    "Cumulative Worldwide Gross": 262797249, "Runtime": 104},
    }

    @staticmethod
    def _fake_scrape(self, imdb_id):
        return Tests._FAKE_IMDB.get(imdb_id, {
            "Director": None, "Budget": None,
            "Cumulative Worldwide Gross": None, "Runtime": None,
        })

    def test_links_init_merges_movies_and_handles_bad_files(self, tmp_path=None):
        links = Links("links.csv")
        assert isinstance(links.data, list)
        row = links._link_by_movie_id(1)
        assert isinstance(row, dict) and isinstance(row["title"], str)
        assert row["title"] != f"Movie {row['movieId']}" 

        try:
            Links("does_not_exist.csv")
            assert False, "expected FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_get_imdb_types_sorting_and_error_handling(self):
        links = Links("links.csv")
        links.imdb_cache = {}  

        orig_scrape = Links._scrape_imdb
        Links._scrape_imdb = self._fake_scrape
        try:
            result = links.get_imdb([1, 2], ["Director", "Budget"])
        finally:
            Links._scrape_imdb = orig_scrape  

        assert isinstance(result, list)
        assert all(isinstance(row, list) for row in result)
        assert all(isinstance(row[0], int) for row in result)
        assert [row[0] for row in result] == sorted([row[0] for row in result], reverse=True)

        def mock_connection_error(*args, **kwargs):
            raise ConnectionError("down")

        orig_scrape = Links._scrape_imdb
        Links._scrape_imdb = mock_connection_error
        try:
            stranded = Links("links.csv")
            stranded.imdb_cache = {}
            stranded.get_imdb([1], ["Director"])
            assert False, "expected RuntimeError on connection failure"
        except RuntimeError:
            pass
        finally:
            Links._scrape_imdb = orig_scrape

    def test_average_budget_by_director(self):
        links = Links("links.csv")

        mock_rows = [
            [1, "Director A", 10000000.0],
            [2, "Director A, Director B", 20000000.0]
        ]

        orig_get_imdb = Links.get_imdb
        Links.get_imdb = lambda self, *args, **kwargs: mock_rows
        try:
            result = links.average_budget_by_director(5)
        finally:
            Links.get_imdb = orig_get_imdb

        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())
        assert all(isinstance(v, float) for v in result.values())

        assert result["Director B"] == 20000000.0
        assert result["Director A"] == 15000000.0
        values = list(result.values())
        assert values == sorted(values, reverse=True)
        
        # Повторная подмена для проверки ограничения n
        Links.get_imdb = lambda self, *args, **kwargs: mock_rows
        try:
            limited_result = links.average_budget_by_director(1)
            assert len(limited_result) <= 1
        finally:
            Links.get_imdb = orig_get_imdb

        with pytest.raises(TypeError):
            links.average_budget_by_director("строка_вместо_числа")
            
        with pytest.raises(ValueError):
            links.average_budget_by_director(-1)

    def test_top_directors_and_most_expensive(self):
        links = Links("links.csv")
        links.imdb_cache = {}
        
        orig_scrape = Links._scrape_imdb
        Links._scrape_imdb = self._fake_scrape
        try:
            directors = links.top_directors(5)
            expensive = links.most_expensive(5)
        finally:
            Links._scrape_imdb = orig_scrape

        assert isinstance(directors, dict)
        assert all(isinstance(v, int) for v in directors.values())
        assert list(directors.values()) == sorted(directors.values(), reverse=True)

        assert isinstance(expensive, dict)
        assert all(isinstance(k, str) for k in expensive.keys())  # titles, not ids
        assert list(expensive.values()) == sorted(expensive.values(), reverse=True)

    def test_most_profitable_and_cost_per_minute_manual_calculation(self):
        links = Links("links.csv")
        links.imdb_cache = {}
        
        orig_scrape = Links._scrape_imdb
        Links._scrape_imdb = self._fake_scrape
        try:
            profitable = links.most_profitable(5)
            cost = links.top_cost_per_minute(5)
        finally:
            Links._scrape_imdb = orig_scrape

        toy_story_title = links._link_by_movie_id(1)["title"]
        assert profitable[toy_story_title] == 373554033 - 30000000

        jumanji_title = links._link_by_movie_id(2)["title"]
        assert cost[jumanji_title] == round(65000000 / 104, 2)

    def test_longest_uses_titles_and_sorting(self):
        links = Links("links.csv")
        links.imdb_cache = {}
        
        orig_scrape = Links._scrape_imdb
        Links._scrape_imdb = self._fake_scrape
        try:
            result = links.longest(5)
        finally:
            Links._scrape_imdb = orig_scrape

        assert isinstance(result, dict)
        jumanji_title = links._link_by_movie_id(2)["title"]
        assert result[jumanji_title] == 104
        assert list(result.values()) == sorted(result.values(), reverse=True)

    # Ratings tests

    RATINGS_CSV_CONTENT = """userId,movieId,rating,timestamp
1,10,4.0,883612800
1,20,3.0,915148800
1,30,5.0,946684800
1,40,2.0,978307200
1,50,4.5,978393600
2,10,5.0,883699200
2,20,4.0,915235200
2,30,4.5,946771200
2,40,3.0,978393600
2,50,2.5,978480000
3,10,2.0,883785600
3,20,2.5,915321600
3,30,3.0,946857600
3,40,3.5,978480000
3,50,4.0,978566400
4,10,4.5,883872000
4,20,4.0,915408000
4,30,5.0,946944000
4,40,1.5,978566400
4,50,2.0,978652800
5,10,3.5,883958400
5,20,3.0,915494400
5,30,2.5,947030400
5,40,4.0,978652800
5,50,4.5,978739200
"""

    MOVIES_CSV_CONTENT = """movieId,title,genres
10,GoldenEye (1995),Action|Adventure|Thriller
20,Money Train (1995),Action|Comedy|Crime|Drama|Thriller
30,Shanghai Triad (Yao a yao yao dao waipo qiao) (1995),Crime|Drama
40,Babe (1995),Children|Drama
50,"Usual Suspects, The (1995)",Crime|Thriller
"""

    @pytest.fixture
    def sample_files(self, tmp_path):
        ratings_path = tmp_path / "ratings.csv"
        movies_path = tmp_path / "movies.csv"
        ratings_path.write_text(self.RATINGS_CSV_CONTENT)
        movies_path.write_text(self.MOVIES_CSV_CONTENT)
        return str(ratings_path), str(movies_path)

    @pytest.fixture
    def ratings(self, sample_files):
        return Ratings(sample_files[0], sample_files[1])

    @pytest.fixture
    def movies(self, ratings):
        return Ratings.Movies(ratings)

    @pytest.fixture
    def users(self, ratings):
        return Ratings.Users(ratings)

    def test_movies_dist_by_year(self, movies):
        result = movies.dist_by_year()
        expected = {1998: 5, 1999: 5, 2000: 5, 2001: 10}
        assert result == expected
        assert isinstance(result, dict)
        assert all(isinstance(k, int) for k in result.keys())
        assert all(isinstance(v, int) for v in result.values())
        assert list(result.keys()) == sorted(result.keys())

    def test_movies_dist_by_rating(self, movies):
        result = movies.dist_by_rating()
        expected = {
            "1.5": 1,
            "2.0": 3,
            "2.5": 3,
            "3.0": 4,
            "3.5": 2,
            "4.0": 5,
            "4.5": 4,
            "5.0": 3,
        }
        assert result == expected
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())
        assert all(isinstance(v, int) for v in result.values())
        assert list(result.keys()) == sorted(result.keys())

    def test_movies_top_by_num_of_ratings(self, movies):
        result = movies.top_by_num_of_ratings(3)
        expected = {
            "GoldenEye (1995)": 5,
            "Money Train (1995)": 5,
            "Shanghai Triad (Yao a yao yao dao waipo qiao) (1995)": 5,
        }
        assert result == expected
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())
        assert all(isinstance(v, int) for v in result.values())
        assert list(result.values()) == sorted(result.values(), reverse=True)

    def test_movies_top_by_ratings_average(self, movies):
        result = movies.top_by_ratings(3, metric="average")
        expected = {
            "Shanghai Triad (Yao a yao yao dao waipo qiao) (1995)": 4.0,
            "GoldenEye (1995)": 3.8,
            "Usual Suspects, The (1995)": 3.5,
        }
        assert result == expected
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())
        assert all(isinstance(v, float) for v in result.values())
        assert list(result.values()) == sorted(result.values(), reverse=True)

    def test_movies_top_by_ratings_median(self, movies):
        result = movies.top_by_ratings(3, metric="median")
        expected = {
            "Shanghai Triad (Yao a yao yao dao waipo qiao) (1995)": 4.5,
            "GoldenEye (1995)": 4.0,
            "Usual Suspects, The (1995)": 4.0,
        }
        assert result == expected
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())
        assert all(isinstance(v, float) for v in result.values())
        assert list(result.values()) == sorted(result.values(), reverse=True)

    def test_movies_top_controversial(self, movies):
        result = movies.top_controversial(3)
        expected = {
            "Shanghai Triad (Yao a yao yao dao waipo qiao) (1995)": 1.1,
            "Usual Suspects, The (1995)": 1.1,
            "GoldenEye (1995)": 1.06,
        }
        assert result == expected
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())
        assert all(isinstance(v, float) for v in result.values())
        assert list(result.values()) == sorted(result.values(), reverse=True)

    def test_users_top_by_num_of_ratings(self, users):
        result = users.top_by_num_of_ratings(3)
        expected = {"1": 5, "2": 5, "3": 5}
        assert result == expected
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())
        assert all(isinstance(v, int) for v in result.values())
        assert list(result.values()) == sorted(result.values(), reverse=True)

    def test_users_top_by_ratings_average(self, users):
        result = users.top_by_ratings(3, metric="average")
        expected = {"2": 3.8, "1": 3.7, "5": 3.5}
        assert result == expected
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())
        assert all(isinstance(v, float) for v in result.values())
        assert list(result.values()) == sorted(result.values(), reverse=True)

    def test_users_top_controversial(self, users):
        result = users.top_controversial(3)
        expected = {"4": 1.94, "1": 1.16, "2": 0.86}
        assert result == expected
        assert isinstance(result, dict)
        assert all(isinstance(k, str) for k in result.keys())
        assert all(isinstance(v, float) for v in result.values())
        assert list(result.values()) == sorted(result.values(), reverse=True)


if __name__ == '__main__':
    links = Links('links.csv')
    print(f"Loaded {len(links.data)} links")
    print("First 3 rows:", links.data[:3])

    if links.imdb_cache:
        print(f"\nLoaded imdb_cache.json with {len(links.imdb_cache)} cached movies.")
    else:
        print(
            "\nNo imdb_cache.json found next to links.csv - get_imdb will try "
            "to scrape IMDB live, which may return empty data if IMDB's "
            "anti-bot challenge blocks the request (see "
            "colab_collect_cache_tmdb.py for how to pre-fill the cache from "
            "an environment where IMDB/TMDB aren't network-blocked)."
        )

    print("\nRunning a quick demo on 3 movies...")
    sample_ids = [row["movieId"] for row in links.data[:3]]
    demo = links.get_imdb(
        sample_ids, ["Director", "Budget", "Cumulative Worldwide Gross", "Runtime"]
    )
    for row in demo:
        print(row)