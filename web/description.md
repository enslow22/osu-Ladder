# osu!Lab api documentation

### At its heart, osu!Lab is just a scores database. 

There are two things that separate osu!Lab from other score databases:
- *It stores scores from **all modes**, except for taiko and mania converts.*
- *It stores multiple scores per beatmap per user*

You can register yourself to get your scores fetched by the api. Once you're registered, osu!lb will constantly update itself will all your new scores. 

---

### Mods:

> You have three options for filtering scores by mods:
- ***Exact***
    - Start the mod string with "!", and osu!Lab will find all scores with that __exact__ mod combination.
    - Note that "CL" is a mod, so nomod plays should have the string "CL" if set on stable and nothing if set on lazer.
    - Example: 'mods=!HDHRDT', 'mods=!EZHTHD'.
- ***Including***
    - Start the string of mods to be included with '+'. osu!Lab will return all scores that include those mods.
    - Example: 'mods=+HRHD', 'mods=+EZ+HD+RX'
- ***Excluding***
    - Start the string of mods to be excluded with "-". osu!Lab will return all scores that exclude those mods.
    - Example: "mods=-HD", "mods=-DT-HT-RC"

>You can combine including and excluding mod filters as well.
For example, the string "mods=+HR-HDDT" will return all scores that have HR, except the ones that also have HD or DT    

---

### General Score Filters:

> osu!lb stores the following data for every score in the database:

| Column Name   | Type                                           | Description                                                                                    |
|---------------|------------------------------------------------|------------------------------------------------------------------------------------------------|
| user_id       | int                                            | The user who set the play                                                                      |
| date          | datetime                                       | The date and time the score was submitted in UTC. Formatted as "YYYY-MM-DD HH:MM:SS"           |
| pp            | float                                          | The pp value of the score.                                                                     |
| rank          | Enum('XH', 'X', 'SH', 'S', 'A', 'B', 'C', 'D') | The awarded rank of the score.                                                                 |
| perfect       | bool                                           | If the score has perfect combo                                                                 |
| max_combo     | int                                            | The highest combo achieved in the score                                                        |
| replay        | bool                                           | Does a replay exist on bancho? (This information may be out of date as bancho deletes replays) |
| stable_score  | int                                            | The score amount on stable. (Will be 0 for scores set on lazer)                                |
| lazer_score   | int                                            | The score amount on lazer.                                                                     |
| classic_score | int                                            | The score amount on lazer classic scoring. (Will be -1 for some scores)                        |
| count_miss    | int                                            | The number of misses                                                                           |
| count_50      | int                                            | The number of 50s                                                                              |
| count_100     | int                                            | The number of 100s                                                                             |
| count_300     | int                                            | The number of 300s                                                                             |

- You can filter through these with operators: (=, !=, >, <, <=, >=, /)
- / represents the contains operator and it is used only for rank. The string rank/XHSH will only return scores that are hidden S or hidden SS
- For dates, you can also compare with the format "YYYY-MM-DD" (e.g. date<2024-07-27 will return all scores older than July 27th 2024, 00:00:00)
- You can add multiple filters by separating them with withspace (e.g. "pp<1000 pp>800 rank/XH,SH date<2023-01-01" will return all scores earlier than 2023, with pp values between 800 and 1000, that are XH OR SH rank)


---

### Beatmap Filters

>There is also support for filtering by beatmap attributes. These can be used to filter scores
based on the beatmaps they were played on.

| Column Name   | Type        | Description                      |
|---------------|-------------|----------------------------------|
| beatmap_id    | int         | The id of the beatmap            |
| beatmapset_id | int         | The id of the beatmapset         |
| mapper_id     | int         | The mapper's user id             |
| total_length  | int         | ????                             |
| hit_length    | int         | ????                             |
| count_total   | int         | Total number of objects???       |
| count_normal  | int         | Total number of circles          |
| count_slider  | int         | Total number of sliders          |
| count_spinner | int         | Total number of spinners         |
| hp            | float       | Beatmap Drain                    |
| cs            | float       | Circle Size                      |
| od            | float       | Overall Difficulty               |
| ar            | float       | Approach Rate                    |
| status        | ENUM(1,2,4) | 1: Ranked, 2: Approved, 4: Loved |
| stars         | float       | Star Rating                      |
| bpm           | float       | BPM                              |
| max_combo     | int         | Max combo of the map             |

> Example
> 
> "ar=8 status=1 bpm>250" will return only the ranked maps where the ar=8 and the bpm is greater than 250

---

### Beatmapset Filters

There are also filters for beatmapsets

| Column Name       | Type         | Description                                        |
|-------------------|--------------|----------------------------------------------------|
| beatmapset_id     | int          | The id of the beatmapset                           |
| owner_id          | int          | The owner's user id                                |
| arist             | string       | The artist's name                                  |
| arist_unicode     | string       | The artist's name including unicode characters     |
| title             | string       | Title of the song                                  |
| title_unicode     | string       | The title of the song including unicode characters |
| tags              | List[string] | A list of the tags on the beatmapset               |
| bpm               | float        | BPM                                                |
| versions_avilable | int          | The number of difficulties in the beatmapset       |
| submit_date       | datetime     | When the map was submitted                         |
| last_update       | datetime     | When the map was last updated (May be inaccurate)  |
| genre_id          | int          | The genre id                                       |
| language_id       | int          | The language id                                    |
| nsfw              | bool         | If the map is flagged as nsfw                      |

- Tags can be queried with "/" and separated by commas. The string "tags/vocaloid,kaai,yuki,hd2" will return mapsets that contain all of these tags.
- The genre and language ids are provided by the osu! api, and can be found below. (Maybe I'll turn it into an enum later.)

Example
 
- "owner_id=10332253" will return all beatmapsets that are owned by [Rozemyne](https://osu.ppy.sh/users/10332253)
- "tags/vocaloid,miku bpm>250 submit_date>2020-01-01" will return all beatmapsets where "vocaloid" and "miku" are in the tags,
whose bpm is greater than 250, and were submitted after 2020.
- "language_id=2 will return all beatmapsets that are in English"

### Language and Genre IDs

##### Genres

    ANY = 0
    UNSPECIFIED = 1
    VIDEO_GAME = 2
    ANIME = 3
    ROCK = 4
    POP = 5
    OTHER = 6
    NOVELTY = 7
    HIP_HOP = 9
    ELECTRONIC = 10
    METAL = 11
    CLASSICAL = 12
    FOLK = 13
    JAZZ = 14

##### Languages

    ANY = 0
    UNSPECIFIED = 1
    ENGLISH = 2
    JAPANESE = 3
    CHINESE = 4
    INSTRUMENTAL = 5
    KOREAN = 6
    FRENCH = 7
    GERMAN = 8
    SWEDISH = 9
    SPANISH = 10
    ITALIAN = 11
    RUSSIAN = 12
    POLISH = 13
    OTHER = 14

### Metrics:

> Metrics are how the returned data is sorted. You can sort the data by any one of the following metrics.

    pp
    stable_score
    lazer_score
    classic_score
    accuracy
    date

> You can also sort by descending (default) or ascending