# Blind SQL equivalence labels

Exploratory validation set (not pre-registered). For each row, decide whether the predicted SQL answers
the question the same way as the gold SQL. Fill in `label` in `to_label.csv` (this file is a readable copy).

- `equivalent`: the two queries return the same result on **every valid database state consistent with the
  schema** (keys unique and non-NULL, foreign keys pointing at existing rows, NOT NULL respected; nullable
  columns may be NULL; tables may be empty). Column order and alias names do not matter; row order matters only
  if the gold query has a top-level ORDER BY.
- `not_equivalent`: there is some valid database state where the results differ, and the difference is not
  explained by an ambiguity in the question.
- `ambiguous`: the question admits both readings (e.g. ties, NULL handling, whether an unmatched nullable
  foreign key row should count, 'courses' vs 'course assignments'), so either query is a defensible answer.

Use `notes` for a one-line reason, especially for `not_equivalent` (the kind of database state that separates
them) and `ambiguous` (the two readings). Do not run the queries against the Spider data to decide; the
question is about all valid states, not the one shipped database. Rows are in random order; nothing about
their source is shown on purpose.


## R672 (poker_player)

**Question:** How many distinct nationalities are there?

<details><summary>Schema</summary>

```sql
CREATE TABLE "poker_player" (
"Poker_Player_ID" int,
"People_ID" int,
"Final_Table_Made" real,
"Best_Finish" real,
"Money_Rank" real,
"Earnings" real,
PRIMARY KEY ("Poker_Player_ID"),
FOREIGN KEY ("People_ID") REFERENCES `people`("People_ID")
);
CREATE TABLE "people" (
"People_ID" int,
"Nationality" text,
"Name" text,
"Birth_Date" text,
"Height" real,
PRIMARY KEY ("People_ID")
);
```

</details>

**Gold SQL**

```sql
SELECT count(DISTINCT Nationality) FROM people
```

**Predicted SQL**

```sql
SELECT count(DISTINCT Nationality) FROM people
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R105 (poker_player)

**Question:** What is the average earnings of poker players?

<details><summary>Schema</summary>

```sql
CREATE TABLE "poker_player" (
"Poker_Player_ID" int,
"People_ID" int,
"Final_Table_Made" real,
"Best_Finish" real,
"Money_Rank" real,
"Earnings" real,
PRIMARY KEY ("Poker_Player_ID"),
FOREIGN KEY ("People_ID") REFERENCES `people`("People_ID")
);
CREATE TABLE "people" (
"People_ID" int,
"Nationality" text,
"Name" text,
"Birth_Date" text,
"Height" real,
PRIMARY KEY ("People_ID")
);
```

</details>

**Gold SQL**

```sql
SELECT avg(Earnings) FROM poker_player
```

**Predicted SQL**

```sql
SELECT avg(Earnings) FROM poker_player
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R469 (pets_1)

**Question:** What are the different first names and ages of the students who do have pets?

<details><summary>Schema</summary>

```sql
CREATE TABLE Student (
       StuID    	INTEGER PRIMARY KEY,
       LName		VARCHAR(12),
       Fname		VARCHAR(12),
       Age		INTEGER,
       Sex		VARCHAR(1),
       Major		INTEGER,
       Advisor		INTEGER,
       city_code	VARCHAR(3)
);
CREATE TABLE Has_Pet (
       StuID		INTEGER,
       PetID		INTEGER,
       FOREIGN KEY(PetID) REFERENCES Pets(PetID),
       FOREIGN KEY(StuID) REFERENCES Student(StuID)
);
CREATE TABLE Pets (
       PetID		INTEGER PRIMARY KEY,
       PetType		VARCHAR(20),
       pet_age INTEGER,
       weight REAL
);
```

</details>

**Gold SQL**

```sql
SELECT DISTINCT T1.fname ,  T1.age FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid
```

**Predicted SQL**

```sql
SELECT DISTINCT T1.Fname ,  T1.Age FROM Student AS T1 JOIN has_pet AS T2 ON T1.StuID  =  T2.StuID JOIN pets AS T3 ON T2.PetID  =  T3.PetID
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R135 (tvshow)

**Question:** What is the number of cartoones written by Joseph Kuhr?

<details><summary>Schema</summary>

```sql
CREATE TABLE "TV_Channel" (
"id" text,
"series_name" text,
"Country" text,
"Language" text,
"Content" text,
"Pixel_aspect_ratio_PAR" text,
"Hight_definition_TV" text,
"Pay_per_view_PPV" text,
"Package_Option" text,
PRIMARY KEY ("id")
);
CREATE TABLE "TV_series" (
"id" real,
"Episode" text,
"Air_Date" text,
"Rating" text,
"Share" real,
"18_49_Rating_Share" text,
"Viewers_m" text,
"Weekly_Rank" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
CREATE TABLE "Cartoon" (
"id" real,
"Title" text,
"Directed_by" text,
"Written_by" text,
"Original_air_date" text,
"Production_code" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM Cartoon WHERE Written_by = "Joseph Kuhr";
```

**Predicted SQL**

```sql
SELECT COUNT ( DISTINCT title ) FROM cartoon WHERE written_by  =  "Joseph Kuhr"
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R335 (museum_visit)

**Question:** What are the opening year and staff number of the museum named Plaza Museum?

<details><summary>Schema</summary>

```sql
CREATE TABLE "museum" (
"Museum_ID" int,
"Name" text,
"Num_of_Staff" int,
"Open_Year" text,
PRIMARY KEY ("Museum_ID")
);
CREATE TABLE "visitor" (
"ID" int,
"Name" text,
"Level_of_membership" int,
"Age" int,
PRIMARY KEY ("ID")
);
CREATE TABLE "visit" (
"Museum_ID" int,
"visitor_ID" text,
"Num_of_Ticket" int,
"Total_spent" real,
PRIMARY KEY ("Museum_ID","visitor_ID"),
FOREIGN KEY ("Museum_ID") REFERENCES `museum`("Museum_ID"),
FOREIGN KEY ("visitor_ID") REFERENCES `visitor`("ID")
);
```

</details>

**Gold SQL**

```sql
SELECT Num_of_Staff ,  Open_Year FROM museum WHERE name  =  'Plaza Museum'
```

**Predicted SQL**

```sql
SELECT Open_Year ,  Num_of_Staff FROM museum WHERE Name  =  "Plaza Museum"
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R283 (wta_1)

**Question:** find the number of distinct country codes of all players.

<details><summary>Schema</summary>

```sql
CREATE TABLE players(
    "player_id" INT PRIMARY KEY,
    "first_name" TEXT,
    "last_name" TEXT,
    "hand" TEXT,
    "birth_date" DATE,
    "country_code" TEXT
);
CREATE TABLE matches(
  "best_of" INT,
  "draw_size" INT,
  "loser_age" FLOAT,
  "loser_entry" TEXT,
  "loser_hand" TEXT,
  "loser_ht" INT,
  "loser_id" INT,
  "loser_ioc" TEXT,
  "loser_name" TEXT,
  "loser_rank" INT,
  "loser_rank_points" INT,
  "loser_seed" INT,
  "match_num" INT,
  "minutes" INT,
  "round" TEXT,
  "score" TEXT,
  "surface" TEXT,
  "tourney_date" DATE,
  "tourney_id" TEXT,
  "tourney_level" TEXT,
  "tourney_name" TEXT,
  "winner_age" FLOAT,
  "winner_entry" TEXT,
  "winner_hand" TEXT,
  "winner_ht" INT,
  "winner_id" INT,
  "winner_ioc" TEXT,
  "winner_name" TEXT,
  "winner_rank" INT,
  "winner_rank_points" INT,
  "winner_seed" INT,
  "year" INT,
  FOREIGN KEY(loser_id) REFERENCES players(player_id),
  FOREIGN KEY(winner_id) REFERENCES players(player_id)
);
CREATE TABLE rankings("ranking_date" DATE,"ranking" INT,"player_id" INT,"ranking_points" INT,"tours" INT,FOREIGN KEY(player_id) REFERENCES players(player_id));
```

</details>

**Gold SQL**

```sql
SELECT count(DISTINCT country_code) FROM players
```

**Predicted SQL**

```sql
SELECT count(DISTINCT country_code) FROM players
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R439 (flight_2)

**Question:** What country is Jetblue Airways affiliated with?

<details><summary>Schema</summary>

```sql
CREATE TABLE 'airlines' (
	uid INTEGER PRIMARY KEY, 
	Airline TEXT, 
	Abbreviation TEXT, 
	Country TEXT
);
CREATE TABLE 'airports' (
	City TEXT, 
	AirportCode TEXT PRIMARY KEY, 
	AirportName TEXT, 
	Country TEXT, 
	CountryAbbrev TEXT
);
CREATE TABLE 'flights' (
	Airline INTEGER, 
	FlightNo INTEGER, 
	SourceAirport TEXT, 
	DestAirport TEXT, 
	PRIMARY KEY(Airline, FlightNo),
	FOREIGN KEY (SourceAirport) REFERENCES airports(AirportCode),
	FOREIGN KEY (DestAirport) REFERENCES airports(AirportCode)
);
```

</details>

**Gold SQL**

```sql
SELECT Country FROM AIRLINES WHERE Airline  =  "JetBlue Airways"
```

**Predicted SQL**

```sql
SELECT Country FROM airlines WHERE Airline  =  "Jetblue Airways";
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R385 (student_transcripts_tracking)

**Question:** What is the first, middle, and last name of the first student to register?

<details><summary>Schema</summary>

```sql
CREATE TABLE `Addresses` (
`address_id` INTEGER PRIMARY KEY,
`line_1` VARCHAR(255),
`line_2` VARCHAR(255),
`line_3` VARCHAR(255),
`city` VARCHAR(255),
`zip_postcode` VARCHAR(20),
`state_province_county` VARCHAR(255),
`country` VARCHAR(255),
`other_address_details` VARCHAR(255)
);
CREATE TABLE `Courses` (
`course_id` INTEGER PRIMARY KEY,
`course_name` VARCHAR(255),
`course_description` VARCHAR(255),
`other_details` VARCHAR(255)
);
CREATE TABLE `Departments` (
`department_id` INTEGER PRIMARY KEY,
`department_name` VARCHAR(255),
`department_description` VARCHAR(255),
`other_details` VARCHAR(255)
);
CREATE TABLE `Degree_Programs` (
`degree_program_id` INTEGER PRIMARY KEY,
`department_id` INTEGER NOT NULL,
`degree_summary_name` VARCHAR(255),
`degree_summary_description` VARCHAR(255),
`other_details` VARCHAR(255),
FOREIGN KEY (`department_id` ) REFERENCES `Departments`(`department_id` )
);
CREATE TABLE `Sections` (
`section_id` INTEGER PRIMARY KEY,
`course_id` INTEGER NOT NULL,
`section_name` VARCHAR(255),
`section_description` VARCHAR(255),
`other_details` VARCHAR(255),
FOREIGN KEY (`course_id` ) REFERENCES `Courses`(`course_id` )
);
CREATE TABLE `Semesters` (
`semester_id` INTEGER PRIMARY KEY,
`semester_name` VARCHAR(255),
`semester_description` VARCHAR(255),
`other_details` VARCHAR(255)
);
CREATE TABLE `Students` (
`student_id` INTEGER PRIMARY KEY,
`current_address_id` INTEGER NOT NULL,
`permanent_address_id` INTEGER NOT NULL,
`first_name` VARCHAR(80),
`middle_name` VARCHAR(40),
`last_name` VARCHAR(40),
`cell_mobile_number` VARCHAR(40),
`email_address` VARCHAR(40),
`ssn` VARCHAR(40),
`date_first_registered` DATETIME,
`date_left` DATETIME,
`other_student_details` VARCHAR(255),
FOREIGN KEY (`current_address_id` ) REFERENCES `Addresses`(`address_id` ),
FOREIGN KEY (`permanent_address_id` ) REFERENCES `Addresses`(`address_id` )
);
CREATE TABLE `Student_Enrolment` (
`student_enrolment_id` INTEGER PRIMARY KEY,
`degree_program_id` INTEGER NOT NULL,
`semester_id` INTEGER NOT NULL,
`student_id` INTEGER NOT NULL,
`other_details` VARCHAR(255),
FOREIGN KEY (`degree_program_id` ) REFERENCES `Degree_Programs`(`degree_program_id` ),
FOREIGN KEY (`semester_id` ) REFERENCES `Semesters`(`semester_id` ),
FOREIGN KEY (`student_id` ) REFERENCES `Students`(`student_id` )
);
CREATE TABLE `Student_Enrolment_Courses` (
`student_course_id` INTEGER PRIMARY KEY,
`course_id` INTEGER NOT NULL,
`student_enrolment_id` INTEGER NOT NULL,
FOREIGN KEY (`course_id` ) REFERENCES `Courses`(`course_id` ),
FOREIGN KEY (`student_enrolment_id` ) REFERENCES `Student_Enrolment`(`student_enrolment_id` )
);
CREATE TABLE `Transcripts` (
`transcript_id` INTEGER PRIMARY KEY,
`transcript_date` DATETIME,
`other_details` VARCHAR(255)
);
CREATE TABLE `Transcript_Contents` (
`student_course_id` INTEGER NOT NULL,
`transcript_id` INTEGER NOT NULL,
FOREIGN KEY (`student_course_id` ) REFERENCES `Student_Enrolment_Courses`(`student_course_id` ),
FOREIGN KEY (`transcript_id` ) REFERENCES `Transcripts`(`transcript_id` )
);
```

</details>

**Gold SQL**

```sql
SELECT first_name ,  middle_name ,  last_name FROM Students ORDER BY date_first_registered ASC LIMIT 1
```

**Predicted SQL**

```sql
SELECT first_name ,  middle_name ,  last_name FROM Students ORDER BY date_first_registered ASC LIMIT 1
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R750 (car_1)

**Question:** What is the number of continents?

<details><summary>Schema</summary>

```sql
CREATE TABLE "continents" ( 
	"ContId" INTEGER PRIMARY KEY, 
	"Continent" TEXT 
);
CREATE TABLE "countries" (
	"CountryId" INTEGER PRIMARY KEY, 
	"CountryName" TEXT, 
	"Continent" INTEGER,
	FOREIGN KEY (Continent) REFERENCES continents(ContId)
);
CREATE TABLE "car_makers" ( 
	"Id" INTEGER PRIMARY KEY, 
	"Maker" TEXT, 
	"FullName" TEXT, 
	"Country" TEXT,
	FOREIGN KEY (Country) REFERENCES countries(CountryId)
);
CREATE TABLE "model_list" ( 
	"ModelId" INTEGER PRIMARY KEY, 
	"Maker" INTEGER, 
	"Model" TEXT UNIQUE,
	FOREIGN KEY (Maker) REFERENCES car_makers (Id)

);
CREATE TABLE "car_names" ( 
	"MakeId" INTEGER PRIMARY KEY, 
	"Model" TEXT, 
	"Make" TEXT,
	FOREIGN KEY (Model) REFERENCES model_list (Model)
);
CREATE TABLE "cars_data" (
	"Id" INTEGER PRIMARY KEY, 
	"MPG" TEXT, 
	"Cylinders" INTEGER, 
	"Edispl" REAL, 
	"Horsepower" TEXT, 
	"Weight" INTEGER, 
	"Accelerate" REAL, 
	"Year" INTEGER,
	FOREIGN KEY (Id) REFERENCES car_names (MakeId)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM CONTINENTS;
```

**Predicted SQL**

```sql
SELECT count(*) FROM continents
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R881 (tvshow)

**Question:** What is minimum and maximum share of TV series?

<details><summary>Schema</summary>

```sql
CREATE TABLE "TV_Channel" (
"id" text,
"series_name" text,
"Country" text,
"Language" text,
"Content" text,
"Pixel_aspect_ratio_PAR" text,
"Hight_definition_TV" text,
"Pay_per_view_PPV" text,
"Package_Option" text,
PRIMARY KEY ("id")
);
CREATE TABLE "TV_series" (
"id" real,
"Episode" text,
"Air_Date" text,
"Rating" text,
"Share" real,
"18_49_Rating_Share" text,
"Viewers_m" text,
"Weekly_Rank" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
CREATE TABLE "Cartoon" (
"id" real,
"Title" text,
"Directed_by" text,
"Written_by" text,
"Original_air_date" text,
"Production_code" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
```

</details>

**Gold SQL**

```sql
SELECT max(SHARE) , min(SHARE) FROM TV_series;
```

**Predicted SQL**

```sql
SELECT min(Share) ,  max(Share) FROM TV_series
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R171 (pets_1)

**Question:** Find the first name and age of students who have a pet.

<details><summary>Schema</summary>

```sql
CREATE TABLE Student (
       StuID    	INTEGER PRIMARY KEY,
       LName		VARCHAR(12),
       Fname		VARCHAR(12),
       Age		INTEGER,
       Sex		VARCHAR(1),
       Major		INTEGER,
       Advisor		INTEGER,
       city_code	VARCHAR(3)
);
CREATE TABLE Has_Pet (
       StuID		INTEGER,
       PetID		INTEGER,
       FOREIGN KEY(PetID) REFERENCES Pets(PetID),
       FOREIGN KEY(StuID) REFERENCES Student(StuID)
);
CREATE TABLE Pets (
       PetID		INTEGER PRIMARY KEY,
       PetType		VARCHAR(20),
       pet_age INTEGER,
       weight REAL
);
```

</details>

**Gold SQL**

```sql
SELECT DISTINCT T1.fname ,  T1.age FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid
```

**Predicted SQL**

```sql
SELECT Fname ,  Age FROM Student WHERE StuID IN (SELECT StuID FROM Has_pet)
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R482 (network_1)

**Question:** Return the number of likes that the high schooler named Kyle has.

<details><summary>Schema</summary>

```sql
CREATE TABLE Highschooler(
	ID int primary key, 
	name text, 
	grade int);
CREATE TABLE Friend(
	student_id int, 
	friend_id int,
	primary key (student_id,friend_id),
	foreign key(student_id) references Highschooler(ID),
	foreign key (friend_id) references Highschooler(ID)
);
CREATE TABLE Likes(
	student_id int, 
	liked_id int,
	primary key (student_id, liked_id),
        foreign key (liked_id) references Highschooler(ID),
        foreign key (student_id) references Highschooler(ID)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM Likes AS T1 JOIN Highschooler AS T2 ON T1.student_id  =  T2.id WHERE T2.name  =  "Kyle"
```

**Predicted SQL**

```sql
SELECT count(*) FROM likes AS T1 JOIN highschooler AS T2 ON T1.liked_id  =  T2.id WHERE T2.name  =  "Kyle";
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R352 (voter_1)

**Question:** What are the number of votes from state 'NY' or 'CA'?

<details><summary>Schema</summary>

```sql
CREATE TABLE `AREA_CODE_STATE` (
  `area_code` integer NOT NULL
,  `state` varchar(2) NOT NULL
,  PRIMARY KEY (`area_code`)
);
CREATE TABLE `CONTESTANTS` (
  `contestant_number` integer
,  `contestant_name` varchar(50) NOT NULL
,  PRIMARY KEY (`contestant_number`)
);
CREATE TABLE `VOTES` (
  `vote_id` integer NOT NULL PRIMARY KEY
,  `phone_number` integer NOT NULL
,  `state` varchar(2) NOT NULL
,  `contestant_number` integer NOT NULL
,  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
, 	FOREIGN KEY (`state`) REFERENCES `AREA_CODE_STATE`(`state`)
, 	FOREIGN KEY (`contestant_number`) REFERENCES `CONTESTANTS`(`contestant_number`)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM votes WHERE state  =  'NY' OR state  =  'CA'
```

**Predicted SQL**

```sql
SELECT count(*) FROM votes WHERE state  =  "NY" OR state  =  "CA"
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R236 (dog_kennels)

**Question:** What are the arriving date and the departing date of all the dogs?

<details><summary>Schema</summary>

```sql
CREATE TABLE `Breeds` (
`breed_code` VARCHAR(10) PRIMARY KEY ,
`breed_name` VARCHAR(80)
);
CREATE TABLE `Charges` (
`charge_id` INTEGER PRIMARY KEY ,
`charge_type` VARCHAR(10),
`charge_amount` DECIMAL(19,4)
);
CREATE TABLE `Sizes` (
`size_code` VARCHAR(10) PRIMARY KEY ,
`size_description` VARCHAR(80)
);
CREATE TABLE `Treatment_Types` (
`treatment_type_code` VARCHAR(10) PRIMARY KEY ,
`treatment_type_description` VARCHAR(80)
);
CREATE TABLE `Owners` (
`owner_id` INTEGER PRIMARY KEY ,
`first_name` VARCHAR(50),
`last_name` VARCHAR(50),
`street` VARCHAR(50),
`city` VARCHAR(50),
`state` VARCHAR(20),
`zip_code` VARCHAR(20),
`email_address` VARCHAR(50),
`home_phone` VARCHAR(20),
`cell_number` VARCHAR(20)
);
CREATE TABLE `Dogs` (
`dog_id` INTEGER PRIMARY KEY ,
`owner_id` INTEGER NOT NULL,
`abandoned_yn` VARCHAR(1),
`breed_code` VARCHAR(10) NOT NULL,
`size_code` VARCHAR(10) NOT NULL,
`name` VARCHAR(50),
`age` VARCHAR(20),
`date_of_birth` DATETIME,
`gender` VARCHAR(1),
`weight` VARCHAR(20),
`date_arrived` DATETIME,
`date_adopted` DATETIME,
`date_departed` DATETIME,
FOREIGN KEY (`breed_code` ) REFERENCES `Breeds`(`breed_code` ),
FOREIGN KEY (`size_code` ) REFERENCES `Sizes`(`size_code` ),
FOREIGN KEY (`owner_id` ) REFERENCES `Owners`(`owner_id` ),
FOREIGN KEY (`owner_id` ) REFERENCES `Owners`(`owner_id` )
);
CREATE TABLE `Professionals` (
`professional_id` INTEGER PRIMARY KEY ,
`role_code` VARCHAR(10) NOT NULL,
`first_name` VARCHAR(50),
`street` VARCHAR(50),
`city` VARCHAR(50),
`state` VARCHAR(20),
`zip_code` VARCHAR(20),
`last_name` VARCHAR(50),
`email_address` VARCHAR(50),
`home_phone` VARCHAR(20),
`cell_number` VARCHAR(20)
);
CREATE TABLE `Treatments` (
`treatment_id` INTEGER PRIMARY KEY ,
`dog_id` INTEGER NOT NULL,
`professional_id` INTEGER NOT NULL,
`treatment_type_code` VARCHAR(10) NOT NULL,
`date_of_treatment` DATETIME,
`cost_of_treatment` DECIMAL(19,4),
FOREIGN KEY (`treatment_type_code` ) REFERENCES `Treatment_Types`(`treatment_type_code` ),
FOREIGN KEY (`professional_id` ) REFERENCES `Professionals`(`professional_id` ),
FOREIGN KEY (`dog_id` ) REFERENCES `Dogs`(`dog_id` )
);
```

</details>

**Gold SQL**

```sql
SELECT date_arrived ,  date_departed FROM Dogs
```

**Predicted SQL**

```sql
SELECT date_arrived ,  date_departed FROM dogs
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R424 (network_1)

**Question:** How many likes does Kyle have?

<details><summary>Schema</summary>

```sql
CREATE TABLE Highschooler(
	ID int primary key, 
	name text, 
	grade int);
CREATE TABLE Friend(
	student_id int, 
	friend_id int,
	primary key (student_id,friend_id),
	foreign key(student_id) references Highschooler(ID),
	foreign key (friend_id) references Highschooler(ID)
);
CREATE TABLE Likes(
	student_id int, 
	liked_id int,
	primary key (student_id, liked_id),
        foreign key (liked_id) references Highschooler(ID),
        foreign key (student_id) references Highschooler(ID)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM Likes AS T1 JOIN Highschooler AS T2 ON T1.student_id  =  T2.id WHERE T2.name  =  "Kyle"
```

**Predicted SQL**

```sql
SELECT count(*) FROM likes AS T1 JOIN highschooler AS T2 ON T1.liked_id  =  T2.id WHERE T2.name  =  "Kyle";
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R581 (flight_2)

**Question:** What is the total number of airlines?

<details><summary>Schema</summary>

```sql
CREATE TABLE 'airlines' (
	uid INTEGER PRIMARY KEY, 
	Airline TEXT, 
	Abbreviation TEXT, 
	Country TEXT
);
CREATE TABLE 'airports' (
	City TEXT, 
	AirportCode TEXT PRIMARY KEY, 
	AirportName TEXT, 
	Country TEXT, 
	CountryAbbrev TEXT
);
CREATE TABLE 'flights' (
	Airline INTEGER, 
	FlightNo INTEGER, 
	SourceAirport TEXT, 
	DestAirport TEXT, 
	PRIMARY KEY(Airline, FlightNo),
	FOREIGN KEY (SourceAirport) REFERENCES airports(AirportCode),
	FOREIGN KEY (DestAirport) REFERENCES airports(AirportCode)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM AIRLINES
```

**Predicted SQL**

```sql
SELECT count(*) FROM airlines
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R337 (network_1)

**Question:** Show the ID of the high schooler named Kyle.

<details><summary>Schema</summary>

```sql
CREATE TABLE Highschooler(
	ID int primary key, 
	name text, 
	grade int);
CREATE TABLE Friend(
	student_id int, 
	friend_id int,
	primary key (student_id,friend_id),
	foreign key(student_id) references Highschooler(ID),
	foreign key (friend_id) references Highschooler(ID)
);
CREATE TABLE Likes(
	student_id int, 
	liked_id int,
	primary key (student_id, liked_id),
        foreign key (liked_id) references Highschooler(ID),
        foreign key (student_id) references Highschooler(ID)
);
```

</details>

**Gold SQL**

```sql
SELECT ID FROM Highschooler WHERE name  =  "Kyle"
```

**Predicted SQL**

```sql
SELECT T1.id FROM highschooler AS T1 JOIN friend AS T2 ON T1.id  =  T2.student_id WHERE name  =  "Kyle"
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R113 (network_1)

**Question:** How many likes correspond to each student id?

<details><summary>Schema</summary>

```sql
CREATE TABLE Highschooler(
	ID int primary key, 
	name text, 
	grade int);
CREATE TABLE Friend(
	student_id int, 
	friend_id int,
	primary key (student_id,friend_id),
	foreign key(student_id) references Highschooler(ID),
	foreign key (friend_id) references Highschooler(ID)
);
CREATE TABLE Likes(
	student_id int, 
	liked_id int,
	primary key (student_id, liked_id),
        foreign key (liked_id) references Highschooler(ID),
        foreign key (student_id) references Highschooler(ID)
);
```

</details>

**Gold SQL**

```sql
SELECT student_id ,  count(*) FROM Likes GROUP BY student_id
```

**Predicted SQL**

```sql
SELECT T1.student_id ,  count(*) FROM Likes AS T1 JOIN highschooler AS T2 ON T1.student_id  =  T2.id GROUP BY T1.student_id
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R334 (network_1)

**Question:** What is the grade of each high schooler?

<details><summary>Schema</summary>

```sql
CREATE TABLE Highschooler(
	ID int primary key, 
	name text, 
	grade int);
CREATE TABLE Friend(
	student_id int, 
	friend_id int,
	primary key (student_id,friend_id),
	foreign key(student_id) references Highschooler(ID),
	foreign key (friend_id) references Highschooler(ID)
);
CREATE TABLE Likes(
	student_id int, 
	liked_id int,
	primary key (student_id, liked_id),
        foreign key (liked_id) references Highschooler(ID),
        foreign key (student_id) references Highschooler(ID)
);
```

</details>

**Gold SQL**

```sql
SELECT grade FROM Highschooler
```

**Predicted SQL**

```sql
SELECT grade FROM highschooler
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R426 (orchestra)

**Question:** What are the names of conductors, sorted descending by the number of years they have worked?

<details><summary>Schema</summary>

```sql
CREATE TABLE "conductor" (
"Conductor_ID" int,
"Name" text,
"Age" int,
"Nationality" text,
"Year_of_Work" int,
PRIMARY KEY ("Conductor_ID")
);
CREATE TABLE "orchestra" (
"Orchestra_ID" int,
"Orchestra" text,
"Conductor_ID" int,
"Record_Company" text,
"Year_of_Founded" real,
"Major_Record_Format" text,
PRIMARY KEY ("Orchestra_ID"),
FOREIGN KEY (`Conductor_ID`) REFERENCES `conductor`(`Conductor_ID`)
);
CREATE TABLE "performance" (
"Performance_ID" int,
"Orchestra_ID" int,
"Type" text,
"Date" text,
"Official_ratings_(millions)" real,
"Weekly_rank" text,
"Share" text,
PRIMARY KEY ("Performance_ID"),
FOREIGN KEY (`Orchestra_ID`) REFERENCES `orchestra`(`Orchestra_ID`)
);
CREATE TABLE "show" (
"Show_ID" int,
"Performance_ID" int,
"If_first_show" bool,
"Result" text,
"Attendance" real,
FOREIGN KEY (`Performance_ID`) REFERENCES `performance`(`Performance_ID`)
);
```

</details>

**Gold SQL**

```sql
SELECT Name FROM conductor ORDER BY Year_of_Work DESC
```

**Predicted SQL**

```sql
SELECT Name FROM conductor ORDER BY YEAR_of_Work DESC
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R632 (poker_player)

**Question:** What are the names of people who are not from Russia?

<details><summary>Schema</summary>

```sql
CREATE TABLE "poker_player" (
"Poker_Player_ID" int,
"People_ID" int,
"Final_Table_Made" real,
"Best_Finish" real,
"Money_Rank" real,
"Earnings" real,
PRIMARY KEY ("Poker_Player_ID"),
FOREIGN KEY ("People_ID") REFERENCES `people`("People_ID")
);
CREATE TABLE "people" (
"People_ID" int,
"Nationality" text,
"Name" text,
"Birth_Date" text,
"Height" real,
PRIMARY KEY ("People_ID")
);
```

</details>

**Gold SQL**

```sql
SELECT Name FROM people WHERE Nationality != "Russia"
```

**Predicted SQL**

```sql
SELECT Name FROM people WHERE Nationality != 'Russia'
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R265 (car_1)

**Question:** In which years cars were produced weighing no less than 3000 and no more than 4000?

<details><summary>Schema</summary>

```sql
CREATE TABLE "continents" ( 
	"ContId" INTEGER PRIMARY KEY, 
	"Continent" TEXT 
);
CREATE TABLE "countries" (
	"CountryId" INTEGER PRIMARY KEY, 
	"CountryName" TEXT, 
	"Continent" INTEGER,
	FOREIGN KEY (Continent) REFERENCES continents(ContId)
);
CREATE TABLE "car_makers" ( 
	"Id" INTEGER PRIMARY KEY, 
	"Maker" TEXT, 
	"FullName" TEXT, 
	"Country" TEXT,
	FOREIGN KEY (Country) REFERENCES countries(CountryId)
);
CREATE TABLE "model_list" ( 
	"ModelId" INTEGER PRIMARY KEY, 
	"Maker" INTEGER, 
	"Model" TEXT UNIQUE,
	FOREIGN KEY (Maker) REFERENCES car_makers (Id)

);
CREATE TABLE "car_names" ( 
	"MakeId" INTEGER PRIMARY KEY, 
	"Model" TEXT, 
	"Make" TEXT,
	FOREIGN KEY (Model) REFERENCES model_list (Model)
);
CREATE TABLE "cars_data" (
	"Id" INTEGER PRIMARY KEY, 
	"MPG" TEXT, 
	"Cylinders" INTEGER, 
	"Edispl" REAL, 
	"Horsepower" TEXT, 
	"Weight" INTEGER, 
	"Accelerate" REAL, 
	"Year" INTEGER,
	FOREIGN KEY (Id) REFERENCES car_names (MakeId)
);
```

</details>

**Gold SQL**

```sql
SELECT DISTINCT T1.Year FROM CARS_DATA AS T1 WHERE T1.Weight  >  3000 AND T1.weight  <  4000;
```

**Predicted SQL**

```sql
SELECT DISTINCT YEAR FROM cars_data WHERE Weight BETWEEN 3000 AND 4000
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R907 (pets_1)

**Question:** What is the last name of the student who has a cat that is 3 years old?

<details><summary>Schema</summary>

```sql
CREATE TABLE Student (
       StuID    	INTEGER PRIMARY KEY,
       LName		VARCHAR(12),
       Fname		VARCHAR(12),
       Age		INTEGER,
       Sex		VARCHAR(1),
       Major		INTEGER,
       Advisor		INTEGER,
       city_code	VARCHAR(3)
);
CREATE TABLE Has_Pet (
       StuID		INTEGER,
       PetID		INTEGER,
       FOREIGN KEY(PetID) REFERENCES Pets(PetID),
       FOREIGN KEY(StuID) REFERENCES Student(StuID)
);
CREATE TABLE Pets (
       PetID		INTEGER PRIMARY KEY,
       PetType		VARCHAR(20),
       pet_age INTEGER,
       weight REAL
);
```

</details>

**Gold SQL**

```sql
SELECT T1.lname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pet_age  =  3 AND T3.pettype  =  'cat'
```

**Predicted SQL**

```sql
SELECT t1.lname FROM student AS t1 JOIN has_pet AS t2 ON t1.stuid  =  t2.stuid JOIN pets AS t3 ON t2.petid  =  t3.petid WHERE t3.pet_age  =  3
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R948 (car_1)

**Question:** What is the average horsepower of the cars before 1980?

<details><summary>Schema</summary>

```sql
CREATE TABLE "continents" ( 
	"ContId" INTEGER PRIMARY KEY, 
	"Continent" TEXT 
);
CREATE TABLE "countries" (
	"CountryId" INTEGER PRIMARY KEY, 
	"CountryName" TEXT, 
	"Continent" INTEGER,
	FOREIGN KEY (Continent) REFERENCES continents(ContId)
);
CREATE TABLE "car_makers" ( 
	"Id" INTEGER PRIMARY KEY, 
	"Maker" TEXT, 
	"FullName" TEXT, 
	"Country" TEXT,
	FOREIGN KEY (Country) REFERENCES countries(CountryId)
);
CREATE TABLE "model_list" ( 
	"ModelId" INTEGER PRIMARY KEY, 
	"Maker" INTEGER, 
	"Model" TEXT UNIQUE,
	FOREIGN KEY (Maker) REFERENCES car_makers (Id)

);
CREATE TABLE "car_names" ( 
	"MakeId" INTEGER PRIMARY KEY, 
	"Model" TEXT, 
	"Make" TEXT,
	FOREIGN KEY (Model) REFERENCES model_list (Model)
);
CREATE TABLE "cars_data" (
	"Id" INTEGER PRIMARY KEY, 
	"MPG" TEXT, 
	"Cylinders" INTEGER, 
	"Edispl" REAL, 
	"Horsepower" TEXT, 
	"Weight" INTEGER, 
	"Accelerate" REAL, 
	"Year" INTEGER,
	FOREIGN KEY (Id) REFERENCES car_names (MakeId)
);
```

</details>

**Gold SQL**

```sql
SELECT avg(horsepower) FROM CARS_DATA WHERE YEAR  <  1980;
```

**Predicted SQL**

```sql
SELECT avg(Horsepower) FROM cars_data WHERE YEAR  <  1980
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R102 (car_1)

**Question:** What are the different years in which there were cars produced that weighed less than 4000 and also cars that weighted more than 3000?

<details><summary>Schema</summary>

```sql
CREATE TABLE "continents" ( 
	"ContId" INTEGER PRIMARY KEY, 
	"Continent" TEXT 
);
CREATE TABLE "countries" (
	"CountryId" INTEGER PRIMARY KEY, 
	"CountryName" TEXT, 
	"Continent" INTEGER,
	FOREIGN KEY (Continent) REFERENCES continents(ContId)
);
CREATE TABLE "car_makers" ( 
	"Id" INTEGER PRIMARY KEY, 
	"Maker" TEXT, 
	"FullName" TEXT, 
	"Country" TEXT,
	FOREIGN KEY (Country) REFERENCES countries(CountryId)
);
CREATE TABLE "model_list" ( 
	"ModelId" INTEGER PRIMARY KEY, 
	"Maker" INTEGER, 
	"Model" TEXT UNIQUE,
	FOREIGN KEY (Maker) REFERENCES car_makers (Id)

);
CREATE TABLE "car_names" ( 
	"MakeId" INTEGER PRIMARY KEY, 
	"Model" TEXT, 
	"Make" TEXT,
	FOREIGN KEY (Model) REFERENCES model_list (Model)
);
CREATE TABLE "cars_data" (
	"Id" INTEGER PRIMARY KEY, 
	"MPG" TEXT, 
	"Cylinders" INTEGER, 
	"Edispl" REAL, 
	"Horsepower" TEXT, 
	"Weight" INTEGER, 
	"Accelerate" REAL, 
	"Year" INTEGER,
	FOREIGN KEY (Id) REFERENCES car_names (MakeId)
);
```

</details>

**Gold SQL**

```sql
SELECT DISTINCT T1.Year FROM CARS_DATA AS T1 WHERE T1.Weight  >  3000 AND T1.weight  <  4000;
```

**Predicted SQL**

```sql
SELECT DISTINCT YEAR FROM cars_data WHERE Weight  <  4000 INTERSECT SELECT DISTINCT YEAR FROM cars_data WHERE Weight  >  3000
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R160 (dog_kennels)

**Question:** How many dogs went through any treatments?

<details><summary>Schema</summary>

```sql
CREATE TABLE `Breeds` (
`breed_code` VARCHAR(10) PRIMARY KEY ,
`breed_name` VARCHAR(80)
);
CREATE TABLE `Charges` (
`charge_id` INTEGER PRIMARY KEY ,
`charge_type` VARCHAR(10),
`charge_amount` DECIMAL(19,4)
);
CREATE TABLE `Sizes` (
`size_code` VARCHAR(10) PRIMARY KEY ,
`size_description` VARCHAR(80)
);
CREATE TABLE `Treatment_Types` (
`treatment_type_code` VARCHAR(10) PRIMARY KEY ,
`treatment_type_description` VARCHAR(80)
);
CREATE TABLE `Owners` (
`owner_id` INTEGER PRIMARY KEY ,
`first_name` VARCHAR(50),
`last_name` VARCHAR(50),
`street` VARCHAR(50),
`city` VARCHAR(50),
`state` VARCHAR(20),
`zip_code` VARCHAR(20),
`email_address` VARCHAR(50),
`home_phone` VARCHAR(20),
`cell_number` VARCHAR(20)
);
CREATE TABLE `Dogs` (
`dog_id` INTEGER PRIMARY KEY ,
`owner_id` INTEGER NOT NULL,
`abandoned_yn` VARCHAR(1),
`breed_code` VARCHAR(10) NOT NULL,
`size_code` VARCHAR(10) NOT NULL,
`name` VARCHAR(50),
`age` VARCHAR(20),
`date_of_birth` DATETIME,
`gender` VARCHAR(1),
`weight` VARCHAR(20),
`date_arrived` DATETIME,
`date_adopted` DATETIME,
`date_departed` DATETIME,
FOREIGN KEY (`breed_code` ) REFERENCES `Breeds`(`breed_code` ),
FOREIGN KEY (`size_code` ) REFERENCES `Sizes`(`size_code` ),
FOREIGN KEY (`owner_id` ) REFERENCES `Owners`(`owner_id` ),
FOREIGN KEY (`owner_id` ) REFERENCES `Owners`(`owner_id` )
);
CREATE TABLE `Professionals` (
`professional_id` INTEGER PRIMARY KEY ,
`role_code` VARCHAR(10) NOT NULL,
`first_name` VARCHAR(50),
`street` VARCHAR(50),
`city` VARCHAR(50),
`state` VARCHAR(20),
`zip_code` VARCHAR(20),
`last_name` VARCHAR(50),
`email_address` VARCHAR(50),
`home_phone` VARCHAR(20),
`cell_number` VARCHAR(20)
);
CREATE TABLE `Treatments` (
`treatment_id` INTEGER PRIMARY KEY ,
`dog_id` INTEGER NOT NULL,
`professional_id` INTEGER NOT NULL,
`treatment_type_code` VARCHAR(10) NOT NULL,
`date_of_treatment` DATETIME,
`cost_of_treatment` DECIMAL(19,4),
FOREIGN KEY (`treatment_type_code` ) REFERENCES `Treatment_Types`(`treatment_type_code` ),
FOREIGN KEY (`professional_id` ) REFERENCES `Professionals`(`professional_id` ),
FOREIGN KEY (`dog_id` ) REFERENCES `Dogs`(`dog_id` )
);
```

</details>

**Gold SQL**

```sql
SELECT count(DISTINCT dog_id) FROM Treatments
```

**Predicted SQL**

```sql
SELECT count(DISTINCT t2.dog_id) FROM dogs AS t2 JOIN treatments AS t1 ON t2.dog_id  =  t1.dog_id
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R617 (pets_1)

**Question:** What are the different first names and ages of the students who do have pets?

<details><summary>Schema</summary>

```sql
CREATE TABLE Student (
       StuID    	INTEGER PRIMARY KEY,
       LName		VARCHAR(12),
       Fname		VARCHAR(12),
       Age		INTEGER,
       Sex		VARCHAR(1),
       Major		INTEGER,
       Advisor		INTEGER,
       city_code	VARCHAR(3)
);
CREATE TABLE Has_Pet (
       StuID		INTEGER,
       PetID		INTEGER,
       FOREIGN KEY(PetID) REFERENCES Pets(PetID),
       FOREIGN KEY(StuID) REFERENCES Student(StuID)
);
CREATE TABLE Pets (
       PetID		INTEGER PRIMARY KEY,
       PetType		VARCHAR(20),
       pet_age INTEGER,
       weight REAL
);
```

</details>

**Gold SQL**

```sql
SELECT DISTINCT T1.fname ,  T1.age FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid
```

**Predicted SQL**

```sql
SELECT DISTINCT t.Fname ,  t.Age FROM Student AS t JOIN Has_pet AS h ON t.StuID  =  h.StuID JOIN Pets AS p ON h.PetID  =  p.PetID
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R998 (wta_1)

**Question:** How many different loser names are there?

<details><summary>Schema</summary>

```sql
CREATE TABLE players(
    "player_id" INT PRIMARY KEY,
    "first_name" TEXT,
    "last_name" TEXT,
    "hand" TEXT,
    "birth_date" DATE,
    "country_code" TEXT
);
CREATE TABLE matches(
  "best_of" INT,
  "draw_size" INT,
  "loser_age" FLOAT,
  "loser_entry" TEXT,
  "loser_hand" TEXT,
  "loser_ht" INT,
  "loser_id" INT,
  "loser_ioc" TEXT,
  "loser_name" TEXT,
  "loser_rank" INT,
  "loser_rank_points" INT,
  "loser_seed" INT,
  "match_num" INT,
  "minutes" INT,
  "round" TEXT,
  "score" TEXT,
  "surface" TEXT,
  "tourney_date" DATE,
  "tourney_id" TEXT,
  "tourney_level" TEXT,
  "tourney_name" TEXT,
  "winner_age" FLOAT,
  "winner_entry" TEXT,
  "winner_hand" TEXT,
  "winner_ht" INT,
  "winner_id" INT,
  "winner_ioc" TEXT,
  "winner_name" TEXT,
  "winner_rank" INT,
  "winner_rank_points" INT,
  "winner_seed" INT,
  "year" INT,
  FOREIGN KEY(loser_id) REFERENCES players(player_id),
  FOREIGN KEY(winner_id) REFERENCES players(player_id)
);
CREATE TABLE rankings("ranking_date" DATE,"ranking" INT,"player_id" INT,"ranking_points" INT,"tours" INT,FOREIGN KEY(player_id) REFERENCES players(player_id));
```

</details>

**Gold SQL**

```sql
SELECT count(DISTINCT loser_name) FROM matches
```

**Predicted SQL**

```sql
SELECT count(DISTINCT Loser_name) FROM matches
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R947 (poker_player)

**Question:** What are the nationalities that are shared by at least two people?

<details><summary>Schema</summary>

```sql
CREATE TABLE "poker_player" (
"Poker_Player_ID" int,
"People_ID" int,
"Final_Table_Made" real,
"Best_Finish" real,
"Money_Rank" real,
"Earnings" real,
PRIMARY KEY ("Poker_Player_ID"),
FOREIGN KEY ("People_ID") REFERENCES `people`("People_ID")
);
CREATE TABLE "people" (
"People_ID" int,
"Nationality" text,
"Name" text,
"Birth_Date" text,
"Height" real,
PRIMARY KEY ("People_ID")
);
```

</details>

**Gold SQL**

```sql
SELECT Nationality FROM people GROUP BY Nationality HAVING COUNT(*)  >=  2
```

**Predicted SQL**

```sql
SELECT Nationality FROM people GROUP BY Nationality HAVING COUNT(*)  >=  2
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R790 (pets_1)

**Question:** How many pets have a greater weight than 10?

<details><summary>Schema</summary>

```sql
CREATE TABLE Student (
       StuID    	INTEGER PRIMARY KEY,
       LName		VARCHAR(12),
       Fname		VARCHAR(12),
       Age		INTEGER,
       Sex		VARCHAR(1),
       Major		INTEGER,
       Advisor		INTEGER,
       city_code	VARCHAR(3)
);
CREATE TABLE Has_Pet (
       StuID		INTEGER,
       PetID		INTEGER,
       FOREIGN KEY(PetID) REFERENCES Pets(PetID),
       FOREIGN KEY(StuID) REFERENCES Student(StuID)
);
CREATE TABLE Pets (
       PetID		INTEGER PRIMARY KEY,
       PetType		VARCHAR(20),
       pet_age INTEGER,
       weight REAL
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM pets WHERE weight  >  10
```

**Predicted SQL**

```sql
SELECT count(*) FROM pets WHERE weight  >  10
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R289 (network_1)

**Question:** Return the number of likes that the high schooler named Kyle has.

<details><summary>Schema</summary>

```sql
CREATE TABLE Highschooler(
	ID int primary key, 
	name text, 
	grade int);
CREATE TABLE Friend(
	student_id int, 
	friend_id int,
	primary key (student_id,friend_id),
	foreign key(student_id) references Highschooler(ID),
	foreign key (friend_id) references Highschooler(ID)
);
CREATE TABLE Likes(
	student_id int, 
	liked_id int,
	primary key (student_id, liked_id),
        foreign key (liked_id) references Highschooler(ID),
        foreign key (student_id) references Highschooler(ID)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM Likes AS T1 JOIN Highschooler AS T2 ON T1.student_id  =  T2.id WHERE T2.name  =  "Kyle"
```

**Predicted SQL**

```sql
SELECT count(*) FROM likes AS T1 JOIN highschooler AS T2 ON T1.liked_id  =  T2.id WHERE T2.name  =  'Kyle'
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R856 (voter_1)

**Question:** How many states are there?

<details><summary>Schema</summary>

```sql
CREATE TABLE `AREA_CODE_STATE` (
  `area_code` integer NOT NULL
,  `state` varchar(2) NOT NULL
,  PRIMARY KEY (`area_code`)
);
CREATE TABLE `CONTESTANTS` (
  `contestant_number` integer
,  `contestant_name` varchar(50) NOT NULL
,  PRIMARY KEY (`contestant_number`)
);
CREATE TABLE `VOTES` (
  `vote_id` integer NOT NULL PRIMARY KEY
,  `phone_number` integer NOT NULL
,  `state` varchar(2) NOT NULL
,  `contestant_number` integer NOT NULL
,  `created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
, 	FOREIGN KEY (`state`) REFERENCES `AREA_CODE_STATE`(`state`)
, 	FOREIGN KEY (`contestant_number`) REFERENCES `CONTESTANTS`(`contestant_number`)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM area_code_state
```

**Predicted SQL**

```sql
SELECT count(DISTINCT state) FROM area_code_state
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R521 (tvshow)

**Question:** What is the number of cartoones written by Joseph Kuhr?

<details><summary>Schema</summary>

```sql
CREATE TABLE "TV_Channel" (
"id" text,
"series_name" text,
"Country" text,
"Language" text,
"Content" text,
"Pixel_aspect_ratio_PAR" text,
"Hight_definition_TV" text,
"Pay_per_view_PPV" text,
"Package_Option" text,
PRIMARY KEY ("id")
);
CREATE TABLE "TV_series" (
"id" real,
"Episode" text,
"Air_Date" text,
"Rating" text,
"Share" real,
"18_49_Rating_Share" text,
"Viewers_m" text,
"Weekly_Rank" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
CREATE TABLE "Cartoon" (
"id" real,
"Title" text,
"Directed_by" text,
"Written_by" text,
"Original_air_date" text,
"Production_code" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM Cartoon WHERE Written_by = "Joseph Kuhr";
```

**Predicted SQL**

```sql
SELECT COUNT ( DISTINCT title ) FROM cartoon WHERE written_by  =  "Joseph Kuhr";
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R655 (world_1)

**Question:** Return the names of the 3 countries with the fewest people.

<details><summary>Schema</summary>

```sql
CREATE TABLE `city` (
  `ID` integer NOT NULL PRIMARY KEY AUTOINCREMENT
,  `Name` char(35) NOT NULL DEFAULT ''
,  `CountryCode` char(3) NOT NULL DEFAULT ''
,  `District` char(20) NOT NULL DEFAULT ''
,  `Population` integer NOT NULL DEFAULT '0'
,  CONSTRAINT `city_ibfk_1` FOREIGN KEY (`CountryCode`) REFERENCES `country` (`Code`)
);
CREATE TABLE `country` (
  `Code` char(3) NOT NULL DEFAULT ''
,  `Name` char(52) NOT NULL DEFAULT ''
,  `Continent` text  NOT NULL DEFAULT 'Asia'
,  `Region` char(26) NOT NULL DEFAULT ''
,  `SurfaceArea` float(10,2) NOT NULL DEFAULT '0.00'
,  `IndepYear` integer DEFAULT NULL
,  `Population` integer NOT NULL DEFAULT '0'
,  `LifeExpectancy` float(3,1) DEFAULT NULL
,  `GNP` float(10,2) DEFAULT NULL
,  `GNPOld` float(10,2) DEFAULT NULL
,  `LocalName` char(45) NOT NULL DEFAULT ''
,  `GovernmentForm` char(45) NOT NULL DEFAULT ''
,  `HeadOfState` char(60) DEFAULT NULL
,  `Capital` integer DEFAULT NULL
,  `Code2` char(2) NOT NULL DEFAULT ''
,  PRIMARY KEY (`Code`)
);
CREATE TABLE `countrylanguage` (
  `CountryCode` char(3) NOT NULL DEFAULT ''
,  `Language` char(30) NOT NULL DEFAULT ''
,  `IsOfficial` text  NOT NULL DEFAULT 'F'
,  `Percentage` float(4,1) NOT NULL DEFAULT '0.0'
,  PRIMARY KEY (`CountryCode`,`Language`)
,  CONSTRAINT `countryLanguage_ibfk_1` FOREIGN KEY (`CountryCode`) REFERENCES `country` (`Code`)
);
```

</details>

**Gold SQL**

```sql
SELECT Name FROM country ORDER BY Population ASC LIMIT 3
```

**Predicted SQL**

```sql
SELECT Name FROM country ORDER BY Population ASC LIMIT 3
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R652 (wta_1)

**Question:** How many matches were played in 2013 or 2016?

<details><summary>Schema</summary>

```sql
CREATE TABLE players(
    "player_id" INT PRIMARY KEY,
    "first_name" TEXT,
    "last_name" TEXT,
    "hand" TEXT,
    "birth_date" DATE,
    "country_code" TEXT
);
CREATE TABLE matches(
  "best_of" INT,
  "draw_size" INT,
  "loser_age" FLOAT,
  "loser_entry" TEXT,
  "loser_hand" TEXT,
  "loser_ht" INT,
  "loser_id" INT,
  "loser_ioc" TEXT,
  "loser_name" TEXT,
  "loser_rank" INT,
  "loser_rank_points" INT,
  "loser_seed" INT,
  "match_num" INT,
  "minutes" INT,
  "round" TEXT,
  "score" TEXT,
  "surface" TEXT,
  "tourney_date" DATE,
  "tourney_id" TEXT,
  "tourney_level" TEXT,
  "tourney_name" TEXT,
  "winner_age" FLOAT,
  "winner_entry" TEXT,
  "winner_hand" TEXT,
  "winner_ht" INT,
  "winner_id" INT,
  "winner_ioc" TEXT,
  "winner_name" TEXT,
  "winner_rank" INT,
  "winner_rank_points" INT,
  "winner_seed" INT,
  "year" INT,
  FOREIGN KEY(loser_id) REFERENCES players(player_id),
  FOREIGN KEY(winner_id) REFERENCES players(player_id)
);
CREATE TABLE rankings("ranking_date" DATE,"ranking" INT,"player_id" INT,"ranking_points" INT,"tours" INT,FOREIGN KEY(player_id) REFERENCES players(player_id));
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM matches WHERE YEAR  =  2013 OR YEAR  =  2016
```

**Predicted SQL**

```sql
SELECT count(*) FROM matches WHERE year  >=  2013 AND year  <=  2016
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R307 (pets_1)

**Question:** Find the weight of the youngest dog.

<details><summary>Schema</summary>

```sql
CREATE TABLE Student (
       StuID    	INTEGER PRIMARY KEY,
       LName		VARCHAR(12),
       Fname		VARCHAR(12),
       Age		INTEGER,
       Sex		VARCHAR(1),
       Major		INTEGER,
       Advisor		INTEGER,
       city_code	VARCHAR(3)
);
CREATE TABLE Has_Pet (
       StuID		INTEGER,
       PetID		INTEGER,
       FOREIGN KEY(PetID) REFERENCES Pets(PetID),
       FOREIGN KEY(StuID) REFERENCES Student(StuID)
);
CREATE TABLE Pets (
       PetID		INTEGER PRIMARY KEY,
       PetType		VARCHAR(20),
       pet_age INTEGER,
       weight REAL
);
```

</details>

**Gold SQL**

```sql
SELECT weight FROM pets ORDER BY pet_age LIMIT 1
```

**Predicted SQL**

```sql
SELECT max(weight) FROM pets WHERE pet_age  =  ( SELECT min(pet_age) FROM pets )
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R368 (tvshow)

**Question:** List the number of different series names and contents in the TV Channel table.

<details><summary>Schema</summary>

```sql
CREATE TABLE "TV_Channel" (
"id" text,
"series_name" text,
"Country" text,
"Language" text,
"Content" text,
"Pixel_aspect_ratio_PAR" text,
"Hight_definition_TV" text,
"Pay_per_view_PPV" text,
"Package_Option" text,
PRIMARY KEY ("id")
);
CREATE TABLE "TV_series" (
"id" real,
"Episode" text,
"Air_Date" text,
"Rating" text,
"Share" real,
"18_49_Rating_Share" text,
"Viewers_m" text,
"Weekly_Rank" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
CREATE TABLE "Cartoon" (
"id" real,
"Title" text,
"Directed_by" text,
"Written_by" text,
"Original_air_date" text,
"Production_code" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
```

</details>

**Gold SQL**

```sql
SELECT count(DISTINCT series_name) ,  count(DISTINCT content) FROM TV_Channel;
```

**Predicted SQL**

```sql
SELECT count(DISTINCT Content) ,  count(DISTINCT series_name) FROM TV_channel
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R182 (pets_1)

**Question:** Find the weight of the youngest dog.

<details><summary>Schema</summary>

```sql
CREATE TABLE Student (
       StuID    	INTEGER PRIMARY KEY,
       LName		VARCHAR(12),
       Fname		VARCHAR(12),
       Age		INTEGER,
       Sex		VARCHAR(1),
       Major		INTEGER,
       Advisor		INTEGER,
       city_code	VARCHAR(3)
);
CREATE TABLE Has_Pet (
       StuID		INTEGER,
       PetID		INTEGER,
       FOREIGN KEY(PetID) REFERENCES Pets(PetID),
       FOREIGN KEY(StuID) REFERENCES Student(StuID)
);
CREATE TABLE Pets (
       PetID		INTEGER PRIMARY KEY,
       PetType		VARCHAR(20),
       pet_age INTEGER,
       weight REAL
);
```

</details>

**Gold SQL**

```sql
SELECT weight FROM pets ORDER BY pet_age LIMIT 1
```

**Predicted SQL**

```sql
SELECT max(weight) FROM Pets WHERE pet_age  =  (SELECT min(pet_age) FROM pets)
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R242 (tvshow)

**Question:** Find the number of cartoons directed by each of the listed directors.

<details><summary>Schema</summary>

```sql
CREATE TABLE "TV_Channel" (
"id" text,
"series_name" text,
"Country" text,
"Language" text,
"Content" text,
"Pixel_aspect_ratio_PAR" text,
"Hight_definition_TV" text,
"Pay_per_view_PPV" text,
"Package_Option" text,
PRIMARY KEY ("id")
);
CREATE TABLE "TV_series" (
"id" real,
"Episode" text,
"Air_Date" text,
"Rating" text,
"Share" real,
"18_49_Rating_Share" text,
"Viewers_m" text,
"Weekly_Rank" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
CREATE TABLE "Cartoon" (
"id" real,
"Title" text,
"Directed_by" text,
"Written_by" text,
"Original_air_date" text,
"Production_code" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) ,  Directed_by FROM cartoon GROUP BY Directed_by
```

**Predicted SQL**

```sql
SELECT count(*) ,  Directed_by FROM Cartoon GROUP BY Directed_by
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R789 (pets_1)

**Question:** What is the id of the pet owned by the student whose last name is 'Smith'?

<details><summary>Schema</summary>

```sql
CREATE TABLE Student (
       StuID    	INTEGER PRIMARY KEY,
       LName		VARCHAR(12),
       Fname		VARCHAR(12),
       Age		INTEGER,
       Sex		VARCHAR(1),
       Major		INTEGER,
       Advisor		INTEGER,
       city_code	VARCHAR(3)
);
CREATE TABLE Has_Pet (
       StuID		INTEGER,
       PetID		INTEGER,
       FOREIGN KEY(PetID) REFERENCES Pets(PetID),
       FOREIGN KEY(StuID) REFERENCES Student(StuID)
);
CREATE TABLE Pets (
       PetID		INTEGER PRIMARY KEY,
       PetType		VARCHAR(20),
       pet_age INTEGER,
       weight REAL
);
```

</details>

**Gold SQL**

```sql
SELECT T2.petid FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid WHERE T1.Lname  =  'Smith'
```

**Predicted SQL**

```sql
SELECT T1.Petid FROM pets AS T1 JOIN Has_pet AS T2 ON T1.Petid  =  T2.Petid JOIN student AS T3 ON T2.Stuid  =  T3.StuID WHERE T3.Lname  =  "Smith";
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R475 (tvshow)

**Question:** What are the Package Options of the TV Channels whose series names are Sky Radio?

<details><summary>Schema</summary>

```sql
CREATE TABLE "TV_Channel" (
"id" text,
"series_name" text,
"Country" text,
"Language" text,
"Content" text,
"Pixel_aspect_ratio_PAR" text,
"Hight_definition_TV" text,
"Pay_per_view_PPV" text,
"Package_Option" text,
PRIMARY KEY ("id")
);
CREATE TABLE "TV_series" (
"id" real,
"Episode" text,
"Air_Date" text,
"Rating" text,
"Share" real,
"18_49_Rating_Share" text,
"Viewers_m" text,
"Weekly_Rank" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
CREATE TABLE "Cartoon" (
"id" real,
"Title" text,
"Directed_by" text,
"Written_by" text,
"Original_air_date" text,
"Production_code" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
```

</details>

**Gold SQL**

```sql
SELECT Package_Option FROM TV_Channel WHERE series_name = "Sky Radio";
```

**Predicted SQL**

```sql
SELECT package_option FROM tv_channel WHERE series_name  =  "Sky Radio"
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R126 (tvshow)

**Question:** list all cartoon titles and their directors ordered by their air date

<details><summary>Schema</summary>

```sql
CREATE TABLE "TV_Channel" (
"id" text,
"series_name" text,
"Country" text,
"Language" text,
"Content" text,
"Pixel_aspect_ratio_PAR" text,
"Hight_definition_TV" text,
"Pay_per_view_PPV" text,
"Package_Option" text,
PRIMARY KEY ("id")
);
CREATE TABLE "TV_series" (
"id" real,
"Episode" text,
"Air_Date" text,
"Rating" text,
"Share" real,
"18_49_Rating_Share" text,
"Viewers_m" text,
"Weekly_Rank" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
CREATE TABLE "Cartoon" (
"id" real,
"Title" text,
"Directed_by" text,
"Written_by" text,
"Original_air_date" text,
"Production_code" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
```

</details>

**Gold SQL**

```sql
SELECT title ,  Directed_by FROM Cartoon ORDER BY Original_air_date
```

**Predicted SQL**

```sql
SELECT title ,  directed_by FROM cartoon ORDER BY original_air_date
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R269 (pets_1)

**Question:** Find number of pets owned by students who are older than 20.

<details><summary>Schema</summary>

```sql
CREATE TABLE Student (
       StuID    	INTEGER PRIMARY KEY,
       LName		VARCHAR(12),
       Fname		VARCHAR(12),
       Age		INTEGER,
       Sex		VARCHAR(1),
       Major		INTEGER,
       Advisor		INTEGER,
       city_code	VARCHAR(3)
);
CREATE TABLE Has_Pet (
       StuID		INTEGER,
       PetID		INTEGER,
       FOREIGN KEY(PetID) REFERENCES Pets(PetID),
       FOREIGN KEY(StuID) REFERENCES Student(StuID)
);
CREATE TABLE Pets (
       PetID		INTEGER PRIMARY KEY,
       PetType		VARCHAR(20),
       pet_age INTEGER,
       weight REAL
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid WHERE T1.age  >  20
```

**Predicted SQL**

```sql
SELECT count(*) FROM Student AS T1 JOIN Has_Pet AS T2 ON T1.StuID  =  T2.StuID JOIN Pets AS T3 ON T2.PetID  =  T3.PetID WHERE T1.Age  >  20
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R727 (cre_Doc_Template_Mgt)

**Question:** Return the lowest version number, along with its corresponding template type code.

<details><summary>Schema</summary>

```sql
CREATE TABLE Ref_Template_Types (
Template_Type_Code CHAR(15) NOT NULL,
Template_Type_Description VARCHAR(255) NOT NULL,
PRIMARY KEY (Template_Type_Code)
);
CREATE TABLE Templates (
Template_ID INTEGER NOT NULL,
Version_Number INTEGER NOT NULL,
Template_Type_Code CHAR(15) NOT NULL,
Date_Effective_From DATETIME,
Date_Effective_To DATETIME,
Template_Details VARCHAR(255) NOT NULL,
PRIMARY KEY (Template_ID),
FOREIGN KEY (Template_Type_Code) REFERENCES Ref_Template_Types (Template_Type_Code)
);
CREATE TABLE Documents (
Document_ID INTEGER NOT NULL,
Template_ID INTEGER,
Document_Name VARCHAR(255),
Document_Description VARCHAR(255),
Other_Details VARCHAR(255),
PRIMARY KEY (Document_ID),
FOREIGN KEY (Template_ID) REFERENCES Templates (Template_ID)
);
CREATE TABLE Paragraphs (
Paragraph_ID INTEGER NOT NULL,
Document_ID INTEGER NOT NULL,
Paragraph_Text VARCHAR(255),
Other_Details VARCHAR(255),
PRIMARY KEY (Paragraph_ID),
FOREIGN KEY (Document_ID) REFERENCES Documents (Document_ID)
);
```

</details>

**Gold SQL**

```sql
SELECT min(Version_Number) ,  template_type_code FROM Templates
```

**Predicted SQL**

```sql
SELECT version_number ,  template_type_code FROM Templates ORDER BY version_number ASC LIMIT 1
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R244 (world_1)

**Question:** What is the continent name which Anguilla belongs to?

<details><summary>Schema</summary>

```sql
CREATE TABLE `city` (
  `ID` integer NOT NULL PRIMARY KEY AUTOINCREMENT
,  `Name` char(35) NOT NULL DEFAULT ''
,  `CountryCode` char(3) NOT NULL DEFAULT ''
,  `District` char(20) NOT NULL DEFAULT ''
,  `Population` integer NOT NULL DEFAULT '0'
,  CONSTRAINT `city_ibfk_1` FOREIGN KEY (`CountryCode`) REFERENCES `country` (`Code`)
);
CREATE TABLE `country` (
  `Code` char(3) NOT NULL DEFAULT ''
,  `Name` char(52) NOT NULL DEFAULT ''
,  `Continent` text  NOT NULL DEFAULT 'Asia'
,  `Region` char(26) NOT NULL DEFAULT ''
,  `SurfaceArea` float(10,2) NOT NULL DEFAULT '0.00'
,  `IndepYear` integer DEFAULT NULL
,  `Population` integer NOT NULL DEFAULT '0'
,  `LifeExpectancy` float(3,1) DEFAULT NULL
,  `GNP` float(10,2) DEFAULT NULL
,  `GNPOld` float(10,2) DEFAULT NULL
,  `LocalName` char(45) NOT NULL DEFAULT ''
,  `GovernmentForm` char(45) NOT NULL DEFAULT ''
,  `HeadOfState` char(60) DEFAULT NULL
,  `Capital` integer DEFAULT NULL
,  `Code2` char(2) NOT NULL DEFAULT ''
,  PRIMARY KEY (`Code`)
);
CREATE TABLE `countrylanguage` (
  `CountryCode` char(3) NOT NULL DEFAULT ''
,  `Language` char(30) NOT NULL DEFAULT ''
,  `IsOfficial` text  NOT NULL DEFAULT 'F'
,  `Percentage` float(4,1) NOT NULL DEFAULT '0.0'
,  PRIMARY KEY (`CountryCode`,`Language`)
,  CONSTRAINT `countryLanguage_ibfk_1` FOREIGN KEY (`CountryCode`) REFERENCES `country` (`Code`)
);
```

</details>

**Gold SQL**

```sql
SELECT Continent FROM country WHERE Name  =  "Anguilla"
```

**Predicted SQL**

```sql
SELECT Continent FROM country WHERE Name  =  "Anguilla";
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R261 (tvshow)

**Question:** What are all of the episodes ordered by ratings?

<details><summary>Schema</summary>

```sql
CREATE TABLE "TV_Channel" (
"id" text,
"series_name" text,
"Country" text,
"Language" text,
"Content" text,
"Pixel_aspect_ratio_PAR" text,
"Hight_definition_TV" text,
"Pay_per_view_PPV" text,
"Package_Option" text,
PRIMARY KEY ("id")
);
CREATE TABLE "TV_series" (
"id" real,
"Episode" text,
"Air_Date" text,
"Rating" text,
"Share" real,
"18_49_Rating_Share" text,
"Viewers_m" text,
"Weekly_Rank" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
CREATE TABLE "Cartoon" (
"id" real,
"Title" text,
"Directed_by" text,
"Written_by" text,
"Original_air_date" text,
"Production_code" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
```

</details>

**Gold SQL**

```sql
SELECT Episode FROM TV_series ORDER BY rating
```

**Predicted SQL**

```sql
SELECT Episode FROM   TV_series ORDER BY Rating DESC
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R957 (museum_visit)

**Question:** What are the opening year and staff number of the museum named Plaza Museum?

<details><summary>Schema</summary>

```sql
CREATE TABLE "museum" (
"Museum_ID" int,
"Name" text,
"Num_of_Staff" int,
"Open_Year" text,
PRIMARY KEY ("Museum_ID")
);
CREATE TABLE "visitor" (
"ID" int,
"Name" text,
"Level_of_membership" int,
"Age" int,
PRIMARY KEY ("ID")
);
CREATE TABLE "visit" (
"Museum_ID" int,
"visitor_ID" text,
"Num_of_Ticket" int,
"Total_spent" real,
PRIMARY KEY ("Museum_ID","visitor_ID"),
FOREIGN KEY ("Museum_ID") REFERENCES `museum`("Museum_ID"),
FOREIGN KEY ("visitor_ID") REFERENCES `visitor`("ID")
);
```

</details>

**Gold SQL**

```sql
SELECT Num_of_Staff ,  Open_Year FROM museum WHERE name  =  'Plaza Museum'
```

**Predicted SQL**

```sql
SELECT open_year ,  num_of_Staff FROM museum WHERE name  =  'Plaza Museum'
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R791 (dog_kennels)

**Question:** List the emails of the professionals who live in the state of Hawaii or the state of Wisconsin.

<details><summary>Schema</summary>

```sql
CREATE TABLE `Breeds` (
`breed_code` VARCHAR(10) PRIMARY KEY ,
`breed_name` VARCHAR(80)
);
CREATE TABLE `Charges` (
`charge_id` INTEGER PRIMARY KEY ,
`charge_type` VARCHAR(10),
`charge_amount` DECIMAL(19,4)
);
CREATE TABLE `Sizes` (
`size_code` VARCHAR(10) PRIMARY KEY ,
`size_description` VARCHAR(80)
);
CREATE TABLE `Treatment_Types` (
`treatment_type_code` VARCHAR(10) PRIMARY KEY ,
`treatment_type_description` VARCHAR(80)
);
CREATE TABLE `Owners` (
`owner_id` INTEGER PRIMARY KEY ,
`first_name` VARCHAR(50),
`last_name` VARCHAR(50),
`street` VARCHAR(50),
`city` VARCHAR(50),
`state` VARCHAR(20),
`zip_code` VARCHAR(20),
`email_address` VARCHAR(50),
`home_phone` VARCHAR(20),
`cell_number` VARCHAR(20)
);
CREATE TABLE `Dogs` (
`dog_id` INTEGER PRIMARY KEY ,
`owner_id` INTEGER NOT NULL,
`abandoned_yn` VARCHAR(1),
`breed_code` VARCHAR(10) NOT NULL,
`size_code` VARCHAR(10) NOT NULL,
`name` VARCHAR(50),
`age` VARCHAR(20),
`date_of_birth` DATETIME,
`gender` VARCHAR(1),
`weight` VARCHAR(20),
`date_arrived` DATETIME,
`date_adopted` DATETIME,
`date_departed` DATETIME,
FOREIGN KEY (`breed_code` ) REFERENCES `Breeds`(`breed_code` ),
FOREIGN KEY (`size_code` ) REFERENCES `Sizes`(`size_code` ),
FOREIGN KEY (`owner_id` ) REFERENCES `Owners`(`owner_id` ),
FOREIGN KEY (`owner_id` ) REFERENCES `Owners`(`owner_id` )
);
CREATE TABLE `Professionals` (
`professional_id` INTEGER PRIMARY KEY ,
`role_code` VARCHAR(10) NOT NULL,
`first_name` VARCHAR(50),
`street` VARCHAR(50),
`city` VARCHAR(50),
`state` VARCHAR(20),
`zip_code` VARCHAR(20),
`last_name` VARCHAR(50),
`email_address` VARCHAR(50),
`home_phone` VARCHAR(20),
`cell_number` VARCHAR(20)
);
CREATE TABLE `Treatments` (
`treatment_id` INTEGER PRIMARY KEY ,
`dog_id` INTEGER NOT NULL,
`professional_id` INTEGER NOT NULL,
`treatment_type_code` VARCHAR(10) NOT NULL,
`date_of_treatment` DATETIME,
`cost_of_treatment` DECIMAL(19,4),
FOREIGN KEY (`treatment_type_code` ) REFERENCES `Treatment_Types`(`treatment_type_code` ),
FOREIGN KEY (`professional_id` ) REFERENCES `Professionals`(`professional_id` ),
FOREIGN KEY (`dog_id` ) REFERENCES `Dogs`(`dog_id` )
);
```

</details>

**Gold SQL**

```sql
SELECT email_address FROM Professionals WHERE state  =  'Hawaii' OR state  =  'Wisconsin'
```

**Predicted SQL**

```sql
SELECT email_address FROM professionals WHERE state  =  'Hawaii' OR state  =  'Wisconsin'
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R769 (network_1)

**Question:** How many likes does Kyle have?

<details><summary>Schema</summary>

```sql
CREATE TABLE Highschooler(
	ID int primary key, 
	name text, 
	grade int);
CREATE TABLE Friend(
	student_id int, 
	friend_id int,
	primary key (student_id,friend_id),
	foreign key(student_id) references Highschooler(ID),
	foreign key (friend_id) references Highschooler(ID)
);
CREATE TABLE Likes(
	student_id int, 
	liked_id int,
	primary key (student_id, liked_id),
        foreign key (liked_id) references Highschooler(ID),
        foreign key (student_id) references Highschooler(ID)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM Likes AS T1 JOIN Highschooler AS T2 ON T1.student_id  =  T2.id WHERE T2.name  =  "Kyle"
```

**Predicted SQL**

```sql
SELECT count(DISTINCT t1.id) FROM likes AS t2 JOIN highschooler AS t1 ON t2.liked_id  =  t1.id WHERE t1.name  =  "Kyle"
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R576 (tvshow)

**Question:** How many cartoons were written by "Joseph Kuhr"?

<details><summary>Schema</summary>

```sql
CREATE TABLE "TV_Channel" (
"id" text,
"series_name" text,
"Country" text,
"Language" text,
"Content" text,
"Pixel_aspect_ratio_PAR" text,
"Hight_definition_TV" text,
"Pay_per_view_PPV" text,
"Package_Option" text,
PRIMARY KEY ("id")
);
CREATE TABLE "TV_series" (
"id" real,
"Episode" text,
"Air_Date" text,
"Rating" text,
"Share" real,
"18_49_Rating_Share" text,
"Viewers_m" text,
"Weekly_Rank" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
CREATE TABLE "Cartoon" (
"id" real,
"Title" text,
"Directed_by" text,
"Written_by" text,
"Original_air_date" text,
"Production_code" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM Cartoon WHERE Written_by = "Joseph Kuhr";
```

**Predicted SQL**

```sql
SELECT COUNT ( DISTINCT title ) FROM Cartoon WHERE written_by  =  "Joseph Kuhr";
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R222 (flight_2)

**Question:** Return the number of United Airlines flights leaving from AHD Airport.

<details><summary>Schema</summary>

```sql
CREATE TABLE 'airlines' (
	uid INTEGER PRIMARY KEY, 
	Airline TEXT, 
	Abbreviation TEXT, 
	Country TEXT
);
CREATE TABLE 'airports' (
	City TEXT, 
	AirportCode TEXT PRIMARY KEY, 
	AirportName TEXT, 
	Country TEXT, 
	CountryAbbrev TEXT
);
CREATE TABLE 'flights' (
	Airline INTEGER, 
	FlightNo INTEGER, 
	SourceAirport TEXT, 
	DestAirport TEXT, 
	PRIMARY KEY(Airline, FlightNo),
	FOREIGN KEY (SourceAirport) REFERENCES airports(AirportCode),
	FOREIGN KEY (DestAirport) REFERENCES airports(AirportCode)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM AIRLINES AS T1 JOIN FLIGHTS AS T2 ON T2.Airline  =  T1.uid WHERE T1.Airline  =  "United Airlines" AND T2.SourceAirport  =  "AHD"
```

**Predicted SQL**

```sql
SELECT count(*) FROM flights AS T1 JOIN airlines AS T2 ON T1.Airline  =  T2.uid WHERE T2.Airline  =  "United Airlines" AND T1.SourceAirport  =  "AHD Airport"
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R780 (wta_1)

**Question:** Find the number of matches happened in each year.

<details><summary>Schema</summary>

```sql
CREATE TABLE players(
    "player_id" INT PRIMARY KEY,
    "first_name" TEXT,
    "last_name" TEXT,
    "hand" TEXT,
    "birth_date" DATE,
    "country_code" TEXT
);
CREATE TABLE matches(
  "best_of" INT,
  "draw_size" INT,
  "loser_age" FLOAT,
  "loser_entry" TEXT,
  "loser_hand" TEXT,
  "loser_ht" INT,
  "loser_id" INT,
  "loser_ioc" TEXT,
  "loser_name" TEXT,
  "loser_rank" INT,
  "loser_rank_points" INT,
  "loser_seed" INT,
  "match_num" INT,
  "minutes" INT,
  "round" TEXT,
  "score" TEXT,
  "surface" TEXT,
  "tourney_date" DATE,
  "tourney_id" TEXT,
  "tourney_level" TEXT,
  "tourney_name" TEXT,
  "winner_age" FLOAT,
  "winner_entry" TEXT,
  "winner_hand" TEXT,
  "winner_ht" INT,
  "winner_id" INT,
  "winner_ioc" TEXT,
  "winner_name" TEXT,
  "winner_rank" INT,
  "winner_rank_points" INT,
  "winner_seed" INT,
  "year" INT,
  FOREIGN KEY(loser_id) REFERENCES players(player_id),
  FOREIGN KEY(winner_id) REFERENCES players(player_id)
);
CREATE TABLE rankings("ranking_date" DATE,"ranking" INT,"player_id" INT,"ranking_points" INT,"tours" INT,FOREIGN KEY(player_id) REFERENCES players(player_id));
```

</details>

**Gold SQL**

```sql
SELECT count(*) ,  YEAR FROM matches GROUP BY YEAR
```

**Predicted SQL**

```sql
SELECT YEAR ,  count(*) FROM MATCHES GROUP BY YEAR
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R449 (museum_visit)

**Question:** What is the average age of the visitors whose membership level is not higher than 4?

<details><summary>Schema</summary>

```sql
CREATE TABLE "museum" (
"Museum_ID" int,
"Name" text,
"Num_of_Staff" int,
"Open_Year" text,
PRIMARY KEY ("Museum_ID")
);
CREATE TABLE "visitor" (
"ID" int,
"Name" text,
"Level_of_membership" int,
"Age" int,
PRIMARY KEY ("ID")
);
CREATE TABLE "visit" (
"Museum_ID" int,
"visitor_ID" text,
"Num_of_Ticket" int,
"Total_spent" real,
PRIMARY KEY ("Museum_ID","visitor_ID"),
FOREIGN KEY ("Museum_ID") REFERENCES `museum`("Museum_ID"),
FOREIGN KEY ("visitor_ID") REFERENCES `visitor`("ID")
);
```

</details>

**Gold SQL**

```sql
SELECT avg(age) FROM visitor WHERE Level_of_membership  <=  4
```

**Predicted SQL**

```sql
SELECT avg(age) FROM visitor WHERE Level_of_membership  <  4
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R478 (car_1)

**Question:** What is the number of cars with a horsepower greater than 150?

<details><summary>Schema</summary>

```sql
CREATE TABLE "continents" ( 
	"ContId" INTEGER PRIMARY KEY, 
	"Continent" TEXT 
);
CREATE TABLE "countries" (
	"CountryId" INTEGER PRIMARY KEY, 
	"CountryName" TEXT, 
	"Continent" INTEGER,
	FOREIGN KEY (Continent) REFERENCES continents(ContId)
);
CREATE TABLE "car_makers" ( 
	"Id" INTEGER PRIMARY KEY, 
	"Maker" TEXT, 
	"FullName" TEXT, 
	"Country" TEXT,
	FOREIGN KEY (Country) REFERENCES countries(CountryId)
);
CREATE TABLE "model_list" ( 
	"ModelId" INTEGER PRIMARY KEY, 
	"Maker" INTEGER, 
	"Model" TEXT UNIQUE,
	FOREIGN KEY (Maker) REFERENCES car_makers (Id)

);
CREATE TABLE "car_names" ( 
	"MakeId" INTEGER PRIMARY KEY, 
	"Model" TEXT, 
	"Make" TEXT,
	FOREIGN KEY (Model) REFERENCES model_list (Model)
);
CREATE TABLE "cars_data" (
	"Id" INTEGER PRIMARY KEY, 
	"MPG" TEXT, 
	"Cylinders" INTEGER, 
	"Edispl" REAL, 
	"Horsepower" TEXT, 
	"Weight" INTEGER, 
	"Accelerate" REAL, 
	"Year" INTEGER,
	FOREIGN KEY (Id) REFERENCES car_names (MakeId)
);
```

</details>

**Gold SQL**

```sql
SELECT count(*) FROM CARS_DATA WHERE horsepower  >  150;
```

**Predicted SQL**

```sql
SELECT count(*) FROM cars_data WHERE Horsepower  >  150
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R165 (network_1)

**Question:** What are the names of the high schoolers and how many friends does each have?

<details><summary>Schema</summary>

```sql
CREATE TABLE Highschooler(
	ID int primary key, 
	name text, 
	grade int);
CREATE TABLE Friend(
	student_id int, 
	friend_id int,
	primary key (student_id,friend_id),
	foreign key(student_id) references Highschooler(ID),
	foreign key (friend_id) references Highschooler(ID)
);
CREATE TABLE Likes(
	student_id int, 
	liked_id int,
	primary key (student_id, liked_id),
        foreign key (liked_id) references Highschooler(ID),
        foreign key (student_id) references Highschooler(ID)
);
```

</details>

**Gold SQL**

```sql
SELECT T2.name ,  count(*) FROM Friend AS T1 JOIN Highschooler AS T2 ON T1.student_id  =  T2.id GROUP BY T1.student_id
```

**Predicted SQL**

```sql
SELECT T2.name ,  count(*) FROM friend AS T1 JOIN highschooler AS T2 ON T1.student_id  =  T2.id GROUP BY T1.student_id
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R605 (tvshow)

**Question:** List the title of all  Cartoons showed on TV Channel with series name "Sky Radio".

<details><summary>Schema</summary>

```sql
CREATE TABLE "TV_Channel" (
"id" text,
"series_name" text,
"Country" text,
"Language" text,
"Content" text,
"Pixel_aspect_ratio_PAR" text,
"Hight_definition_TV" text,
"Pay_per_view_PPV" text,
"Package_Option" text,
PRIMARY KEY ("id")
);
CREATE TABLE "TV_series" (
"id" real,
"Episode" text,
"Air_Date" text,
"Rating" text,
"Share" real,
"18_49_Rating_Share" text,
"Viewers_m" text,
"Weekly_Rank" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
CREATE TABLE "Cartoon" (
"id" real,
"Title" text,
"Directed_by" text,
"Written_by" text,
"Original_air_date" text,
"Production_code" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
```

</details>

**Gold SQL**

```sql
SELECT T2.Title FROM TV_Channel AS T1 JOIN Cartoon AS T2 ON T1.id = T2.Channel WHERE T1.series_name = "Sky Radio";
```

**Predicted SQL**

```sql
SELECT T2.Title FROM Cartoon AS T2 JOIN TV_channel AS T1 ON T2.Channel  =  T1.id WHERE T1.series_name  =  "Sky Radio"
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R864 (flight_2)

**Question:** Which abbreviation corresponds to Jetblue Airways?

<details><summary>Schema</summary>

```sql
CREATE TABLE 'airlines' (
	uid INTEGER PRIMARY KEY, 
	Airline TEXT, 
	Abbreviation TEXT, 
	Country TEXT
);
CREATE TABLE 'airports' (
	City TEXT, 
	AirportCode TEXT PRIMARY KEY, 
	AirportName TEXT, 
	Country TEXT, 
	CountryAbbrev TEXT
);
CREATE TABLE 'flights' (
	Airline INTEGER, 
	FlightNo INTEGER, 
	SourceAirport TEXT, 
	DestAirport TEXT, 
	PRIMARY KEY(Airline, FlightNo),
	FOREIGN KEY (SourceAirport) REFERENCES airports(AirportCode),
	FOREIGN KEY (DestAirport) REFERENCES airports(AirportCode)
);
```

</details>

**Gold SQL**

```sql
SELECT Abbreviation FROM AIRLINES WHERE Airline  =  "JetBlue Airways"
```

**Predicted SQL**

```sql
SELECT Abbreviation FROM airlines WHERE Airline  =  "Jetblue Airways"
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R596 (pets_1)

**Question:** What is the first name and gender of the all the students who have more than one pet?

<details><summary>Schema</summary>

```sql
CREATE TABLE Student (
       StuID    	INTEGER PRIMARY KEY,
       LName		VARCHAR(12),
       Fname		VARCHAR(12),
       Age		INTEGER,
       Sex		VARCHAR(1),
       Major		INTEGER,
       Advisor		INTEGER,
       city_code	VARCHAR(3)
);
CREATE TABLE Has_Pet (
       StuID		INTEGER,
       PetID		INTEGER,
       FOREIGN KEY(PetID) REFERENCES Pets(PetID),
       FOREIGN KEY(StuID) REFERENCES Student(StuID)
);
CREATE TABLE Pets (
       PetID		INTEGER PRIMARY KEY,
       PetType		VARCHAR(20),
       pet_age INTEGER,
       weight REAL
);
```

</details>

**Gold SQL**

```sql
SELECT T1.fname ,  T1.sex FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid GROUP BY T1.stuid HAVING count(*)  >  1
```

**Predicted SQL**

```sql
SELECT T1.Fname ,  T1.Sex FROM Student AS T1 JOIN Has_pet AS T2 ON T1.StuID  =  T2.StuID GROUP BY T1.Fname ,  T1.Sex HAVING COUNT(*)  >  1
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R577 (car_1)

**Question:** What are the different years in which there were cars produced that weighed less than 4000 and also cars that weighted more than 3000?

<details><summary>Schema</summary>

```sql
CREATE TABLE "continents" ( 
	"ContId" INTEGER PRIMARY KEY, 
	"Continent" TEXT 
);
CREATE TABLE "countries" (
	"CountryId" INTEGER PRIMARY KEY, 
	"CountryName" TEXT, 
	"Continent" INTEGER,
	FOREIGN KEY (Continent) REFERENCES continents(ContId)
);
CREATE TABLE "car_makers" ( 
	"Id" INTEGER PRIMARY KEY, 
	"Maker" TEXT, 
	"FullName" TEXT, 
	"Country" TEXT,
	FOREIGN KEY (Country) REFERENCES countries(CountryId)
);
CREATE TABLE "model_list" ( 
	"ModelId" INTEGER PRIMARY KEY, 
	"Maker" INTEGER, 
	"Model" TEXT UNIQUE,
	FOREIGN KEY (Maker) REFERENCES car_makers (Id)

);
CREATE TABLE "car_names" ( 
	"MakeId" INTEGER PRIMARY KEY, 
	"Model" TEXT, 
	"Make" TEXT,
	FOREIGN KEY (Model) REFERENCES model_list (Model)
);
CREATE TABLE "cars_data" (
	"Id" INTEGER PRIMARY KEY, 
	"MPG" TEXT, 
	"Cylinders" INTEGER, 
	"Edispl" REAL, 
	"Horsepower" TEXT, 
	"Weight" INTEGER, 
	"Accelerate" REAL, 
	"Year" INTEGER,
	FOREIGN KEY (Id) REFERENCES car_names (MakeId)
);
```

</details>

**Gold SQL**

```sql
SELECT DISTINCT T1.Year FROM CARS_DATA AS T1 WHERE T1.Weight  >  3000 AND T1.weight  <  4000;
```

**Predicted SQL**

```sql
SELECT DISTINCT YEAR FROM cars_data WHERE Weight  <  4000 OR Weight  >  3000
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 

## R172 (wta_1)

**Question:** Find the number of players for each hand type.

<details><summary>Schema</summary>

```sql
CREATE TABLE players(
    "player_id" INT PRIMARY KEY,
    "first_name" TEXT,
    "last_name" TEXT,
    "hand" TEXT,
    "birth_date" DATE,
    "country_code" TEXT
);
CREATE TABLE matches(
  "best_of" INT,
  "draw_size" INT,
  "loser_age" FLOAT,
  "loser_entry" TEXT,
  "loser_hand" TEXT,
  "loser_ht" INT,
  "loser_id" INT,
  "loser_ioc" TEXT,
  "loser_name" TEXT,
  "loser_rank" INT,
  "loser_rank_points" INT,
  "loser_seed" INT,
  "match_num" INT,
  "minutes" INT,
  "round" TEXT,
  "score" TEXT,
  "surface" TEXT,
  "tourney_date" DATE,
  "tourney_id" TEXT,
  "tourney_level" TEXT,
  "tourney_name" TEXT,
  "winner_age" FLOAT,
  "winner_entry" TEXT,
  "winner_hand" TEXT,
  "winner_ht" INT,
  "winner_id" INT,
  "winner_ioc" TEXT,
  "winner_name" TEXT,
  "winner_rank" INT,
  "winner_rank_points" INT,
  "winner_seed" INT,
  "year" INT,
  FOREIGN KEY(loser_id) REFERENCES players(player_id),
  FOREIGN KEY(winner_id) REFERENCES players(player_id)
);
CREATE TABLE rankings("ranking_date" DATE,"ranking" INT,"player_id" INT,"ranking_points" INT,"tours" INT,FOREIGN KEY(player_id) REFERENCES players(player_id));
```

</details>

**Gold SQL**

```sql
SELECT count(*) ,  hand FROM players GROUP BY hand
```

**Predicted SQL**

```sql
SELECT count(*) ,  hand FROM players GROUP BY hand
```

label: ______ (equivalent / not_equivalent / ambiguous)  
notes: 
